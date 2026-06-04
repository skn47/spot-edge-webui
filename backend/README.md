# Spot Edge Nav — Backend

FastAPI control plane for Phase 2. Bridges browser ↔ ROS 2:

- REST endpoints for mission lifecycle, process control, map listing
- WebSockets for teleop (`/ws/teleop`), state broadcast (`/ws/state`),
  and live process logs (`/ws/logs`)
- A single `rclpy` node running in a background thread publishes
  `/cmd_vel` and `/goal_pose`, and subscribes to `/odometry_map`
- An allowlisted `subprocess.Popen` manager spawns ROS 2 launch files
  for `lidar_stream`, `sensors`, `localization`, `navigation`, and
  `route_manager`

The LiDAR point-cloud bridge is **separate** — it runs as a ROS 2 node
on `ws://host:8765` and is unaffected by this server.

---

## Prerequisites

- ROS 2 Humble installed at `/opt/ros/humble`
- The workspace built: `colcon build --symlink-install` from
  `~/ros2_ws`
- Python 3.10+ available as `python3`
- **A Zenoh router running** (the workspace uses `rmw_zenoh_cpp`).
  Start one in its own terminal *before* launching the backend:
  ```bash
  source /opt/ros/humble/setup.bash
  export RMW_IMPLEMENTATION=rmw_zenoh_cpp
  ros2 run rmw_zenoh_cpp rmw_zenohd
  ```
  Without the router, the backend will still come up but its
  `rclpy` node won't be able to publish `/cmd_vel` / `/goal_pose`
  or receive `/odometry_map` from other peers.

## Install

From the `backend/` directory:

```bash
pip install -r requirements.txt
```

(Use a venv if you prefer — it just needs to share Python with the
system `rclpy` you're using.)

## Run

Use the helper script — it sources ROS, sources the workspace, sets
Zenoh as the RMW, and starts uvicorn:

```bash
./dev_run.sh
```

Or do it manually:

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The server listens on `0.0.0.0:8000`. Verify with:

```bash
curl -s localhost:8000/health
# {"status":"ok","ros_available":true}
```

If `ros_available` is `false`, ROS isn't sourced — re-source and
restart.

## Endpoints

### REST

| Method | Path | Body | Notes |
|---|---|---|---|
| `GET` | `/health` | — | Liveness + `ros_available` |
| `GET` | `/api/maps` | — | Returns allowlisted map names |
| `POST` | `/api/process/{start\|stop\|restart}` | `{ "script_name": "lidar_stream" }` | Allowlist enforced |
| `POST` | `/api/mission/start` | `{ "map_name": "microgrid" }` | Spawns localization → navigation → route_manager |
| `POST` | `/api/mission/stop` | — | Reverse order shutdown |
| `POST` | `/api/mission/pause` | — | Stops route_manager only (planner loses goal) |
| `POST` | `/api/mission/resume` | — | Restarts route_manager |
| `POST` | `/api/mission/home` | — | Publishes `/goal_pose = (0, 0, 0)` |
| `POST` | `/api/mission/estop` | — | Zero velocity + kill nav stack |

### WebSockets

| Path | Direction | Payload |
|---|---|---|
| `/ws/teleop` | client → server | `{ "vx": float, "vy": float, "omega": float }` JSON @ 10 Hz; 200 ms server watchdog zeroes velocity on silence; exclusive (one client at a time) |
| `/ws/state` | server → client | `RobotStateMsg` JSON @ 2 Hz |
| `/ws/logs` | server → client | `LogLine` JSON per stdout/stderr line from spawned processes |

## Allowlisted processes

Defined in `process_manager.py:_ALLOWLIST_BASE`. Anything else is
rejected at the REST handler. `localization` and `navigation` take a
`map_name` that's resolved against `MAP_CATALOG` to inject the
`map_path:=` / `prior_map_path:=` argument.

## Safety notes

- Teleop is server-watchdogged at 200 ms — if the WS goes silent
  longer than that, a zero Twist is published.
- E-stop publishes zero velocity **before** killing the nav stack, so
  the last `/cmd_vel` message the robot sees is a stop.
- CORS is open (`*`) — acceptable on an isolated lab LAN; lock down
  before any internet exposure.
- No auth; this is a lab-demo tool. Treat the port as trusted.

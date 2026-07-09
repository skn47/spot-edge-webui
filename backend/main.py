from __future__ import annotations

import asyncio
import json
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

# Ensure backend/ is on sys.path so sibling modules (models, ros_bridge, etc.)
# are importable regardless of where uvicorn is invoked from.
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from models import (
    LogLine,
    MissionResponse,
    MissionStartRequest,
    OdometryState,
    ProcessRequest,
    ProcessResponse,
    ProcessStatus,
    RobotStateMsg,
    TeleopCmd,
)
from diagnostic import run_diagnostic
from process_manager import ProcessManager
from ros_bridge import RosBridge

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_process_manager = ProcessManager()
_ros_bridge = RosBridge()

# Mission state — user-intent flags only. `mission_active` is derived from
# the actual process statuses inside _state_broadcaster; do not store it here.
_mission_paused = False

# Processes whose collective `running` state defines "mission active".
_MISSION_CORE_PROCESSES = ("localization", "navigation")

# Connected WebSocket client sets
_state_clients: set[WebSocket] = set()
_log_clients: set[WebSocket] = set()

# Teleop exclusivity
_teleop_lock = asyncio.Lock()
_teleop_active = False


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    _process_manager.set_event_loop(loop)
    _ros_bridge.start()

    state_task = asyncio.create_task(_state_broadcaster())
    log_task = asyncio.create_task(_log_broadcaster())

    yield

    state_task.cancel()
    log_task.cancel()
    _ros_bridge.stop()


app = FastAPI(title="Spot Edge Nav Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Background broadcaster tasks
# ---------------------------------------------------------------------------


async def _state_broadcaster() -> None:
    while True:
        await asyncio.sleep(0.5)
        if not _state_clients:
            continue

        odom_raw = _ros_bridge.get_state()
        odom = OdometryState(**odom_raw) if odom_raw else None

        statuses = _process_manager.all_statuses()
        mission_active = all(
            statuses[name].running for name in _MISSION_CORE_PROCESSES
        )

        # If the mission stack died while we were paused, clear the user-intent
        # flag so the UI doesn't get stuck on "Paused" forever.
        global _mission_paused
        if not mission_active and _mission_paused:
            _mission_paused = False

        msg = RobotStateMsg(
            timestamp=time.time(),
            odometry=odom,
            mission_active=mission_active,
            mission_paused=_mission_paused,
            process_statuses=statuses,
        )
        payload = msg.model_dump_json()

        dead: list[WebSocket] = []
        for ws in list(_state_clients):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _state_clients.discard(ws)


async def _log_broadcaster() -> None:
    while True:
        log: LogLine = await _process_manager.log_queue.get()
        if not _log_clients:
            continue
        payload = log.model_dump_json()
        dead: list[WebSocket] = []
        for ws in list(_log_clients):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _log_clients.discard(ws)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/")
async def root():
    return {"service": "spot-edge-nav backend", "status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok", "ros_available": _ros_bridge.available}


@app.get("/api/diagnostic")
async def diagnostic():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_diagnostic)


# ---------------------------------------------------------------------------
# Maps
# ---------------------------------------------------------------------------


@app.get("/api/maps")
async def list_maps():
    return {"maps": _process_manager.map_names}


# ---------------------------------------------------------------------------
# Process control
# ---------------------------------------------------------------------------


@app.post("/api/process/{action}", response_model=ProcessResponse)
async def process_action(
    action: Literal["start", "stop", "restart"],
    body: ProcessRequest,
) -> ProcessResponse:
    name = body.script_name

    if name not in _process_manager.allowlist:
        raise HTTPException(status_code=400, detail=f"'{name}' not in allowlist")

    try:
        if action == "start":
            status = _process_manager.start(name, map_name=body.map_name)
            return ProcessResponse(ok=True, pid=status.pid, message=f"started {name} (pid {status.pid})")
        elif action == "stop":
            status = _process_manager.stop(name)
            return ProcessResponse(ok=True, message=f"stopped {name}")
        elif action == "restart":
            status = _process_manager.restart(name, map_name=body.map_name)
            return ProcessResponse(ok=True, pid=status.pid, message=f"restarted {name} (pid {status.pid})")
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Mission control
# ---------------------------------------------------------------------------


def _mission_core_running() -> bool:
    statuses = _process_manager.all_statuses()
    return all(statuses[name].running for name in _MISSION_CORE_PROCESSES)


@app.post("/api/mission/start", response_model=MissionResponse)
async def mission_start(body: MissionStartRequest) -> MissionResponse:
    global _mission_paused

    if body.map_name not in _process_manager.map_names:
        raise HTTPException(status_code=400, detail=f"unknown map '{body.map_name}'")

    if _mission_core_running():
        raise HTTPException(status_code=409, detail="mission already active")

    try:
        _process_manager.start("localization", map_name=body.map_name)
    except RuntimeError:
        pass  # already running is fine
    await asyncio.sleep(2.0)

    if not _process_manager.status("localization").running:
        return MissionResponse(ok=False, action="start", message="localization failed to start — check logs")

    try:
        _process_manager.start("navigation", map_name=body.map_name)
    except RuntimeError:
        pass
    await asyncio.sleep(2.0)

    if not _process_manager.status("navigation").running:
        _process_manager.stop("localization")
        return MissionResponse(ok=False, action="start", message="navigation failed to start — check logs")

    try:
        _process_manager.start("route_manager")
    except RuntimeError:
        pass

    _mission_paused = False
    return MissionResponse(ok=True, action="start", message=f"mission started with map '{body.map_name}'")


@app.post("/api/mission/stop", response_model=MissionResponse)
async def mission_stop() -> MissionResponse:
    global _mission_paused

    _process_manager.stop("route_manager")
    _process_manager.stop("navigation")
    _process_manager.stop("localization")
    _mission_paused = False
    return MissionResponse(ok=True, action="stop", message="mission stopped")


@app.post("/api/mission/pause", response_model=MissionResponse)
async def mission_pause() -> MissionResponse:
    """
    Pause by stopping route_manager — the planner loses its waypoint stream
    and the robot stops without racing the planner's own /cmd_vel publisher.
    """
    global _mission_paused

    if _mission_paused:
        raise HTTPException(status_code=409, detail="mission already paused")
    if not _mission_core_running():
        raise HTTPException(status_code=409, detail="no active mission to pause")

    _process_manager.stop("route_manager")
    _mission_paused = True
    return MissionResponse(ok=True, action="pause", message="mission paused")


@app.post("/api/mission/resume", response_model=MissionResponse)
async def mission_resume() -> MissionResponse:
    global _mission_paused

    if not _mission_core_running():
        raise HTTPException(status_code=409, detail="no active mission to resume")

    try:
        _process_manager.start("route_manager")
    except RuntimeError:
        pass  # already running is fine
    _mission_paused = False
    return MissionResponse(ok=True, action="resume", message="mission resumed")


@app.post("/api/mission/home", response_model=MissionResponse)
async def mission_home() -> MissionResponse:
    _ros_bridge.publish_goal(0.0, 0.0, 0.0)
    return MissionResponse(ok=True, action="home", message="returning to home (0, 0, 0)")


@app.post("/api/mission/estop", response_model=MissionResponse)
async def mission_estop() -> MissionResponse:
    global _mission_paused

    # Step 1: zero velocity immediately
    _ros_bridge.publish_zero_vel()

    # Step 2: kill navigation stack
    _process_manager.stop("route_manager")
    _process_manager.stop("navigation")
    _process_manager.stop("localization")

    _mission_paused = False
    return MissionResponse(ok=True, action="estop", message="E-stop: velocity zeroed, mission stack stopped")


# ---------------------------------------------------------------------------
# WebSocket: /ws/teleop
# ---------------------------------------------------------------------------


@app.websocket("/ws/teleop")
async def ws_teleop(ws: WebSocket) -> None:
    global _teleop_active

    await ws.accept()

    async with _teleop_lock:
        if _teleop_active:
            await ws.send_text(json.dumps({"type": "error", "message": "teleop_locked"}))
            await ws.close()
            return
        _teleop_active = True

    await ws.send_text(json.dumps({"type": "connected", "message": "teleop active"}))

    watchdog: asyncio.Task | None = None

    def _make_watchdog() -> asyncio.Task:
        async def _dog() -> None:
            await asyncio.sleep(0.2)
            _ros_bridge.publish_zero_vel()
        return asyncio.create_task(_dog())

    try:
        watchdog = _make_watchdog()
        while True:
            raw = await ws.receive_text()
            if watchdog:
                watchdog.cancel()
            try:
                cmd = TeleopCmd.model_validate_json(raw)
                _ros_bridge.publish_cmd_vel(cmd.vx, cmd.vy, cmd.omega)
            except Exception:
                pass
            watchdog = _make_watchdog()
    except WebSocketDisconnect:
        pass
    finally:
        if watchdog:
            watchdog.cancel()
        _ros_bridge.publish_zero_vel()
        async with _teleop_lock:
            _teleop_active = False


# ---------------------------------------------------------------------------
# WebSocket: /ws/logs
# ---------------------------------------------------------------------------


@app.websocket("/ws/logs")
async def ws_logs(ws: WebSocket) -> None:
    await ws.accept()
    _log_clients.add(ws)
    try:
        while True:
            await ws.receive_text()  # keep connection alive; we only push
    except WebSocketDisconnect:
        pass
    finally:
        _log_clients.discard(ws)


# ---------------------------------------------------------------------------
# WebSocket: /ws/state
# ---------------------------------------------------------------------------


@app.websocket("/ws/state")
async def ws_state(ws: WebSocket) -> None:
    await ws.accept()
    _state_clients.add(ws)
    try:
        while True:
            await ws.receive_text()  # keep connection alive; we only push
    except WebSocketDisconnect:
        pass
    finally:
        _state_clients.discard(ws)



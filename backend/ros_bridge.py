from __future__ import annotations

import math
import os
import threading
import time
from typing import Any

# rclpy and message types are imported lazily so the module can be imported
# even if ROS2 is not sourced (the server will degrade gracefully).
try:
    import rclpy
    from geometry_msgs.msg import PoseStamped, Quaternion
    from geometry_msgs.msg import Twist, Vector3
    from nav_msgs.msg import Odometry
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
    from sensor_msgs.msg import CompressedImage
    from std_msgs.msg import Float32
    _ROS_AVAILABLE = True
except ImportError:
    _ROS_AVAILABLE = False

# Multimeter has no heartbeat of its own (BLE link drops and gatttool
# reconnects in owon_node.cpp) — treat a reading as stale once it's this old
# so the UI doesn't keep showing a frozen last-known voltage as if it were live.
VOLTAGE_STALE_AFTER_SEC = 5.0


def _yaw_from_quaternion(q: Any) -> float:
    """Extract yaw (rotation about Z) from a ROS quaternion."""
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


class RosBridge:
    """
    Wraps a single rclpy node running in a background daemon thread.
    All public methods are thread-safe.
    """

    def __init__(self) -> None:
        self._node = None
        self._cmd_vel_pub = None
        self._goal_pub = None
        self._lock = threading.Lock()
        self._latest_odom: dict | None = None
        self._latest_voltage: dict | None = None
        self._latest_frame: bytes | None = None
        self._frame_seq: int = 0
        self._spin_thread: threading.Thread | None = None
        self.available = _ROS_AVAILABLE

    def start(self) -> None:
        if not _ROS_AVAILABLE:
            print("[ros_bridge] rclpy not available — ROS bridge disabled")
            if os.environ.get("MOCK_VOLTAGE") == "1":
                self._start_mock_voltage()
            return

        os.environ.setdefault("RMW_IMPLEMENTATION", "rmw_zenoh_cpp")

        rclpy.init()
        node = rclpy.create_node("web_bridge")
        self._node = node

        self._cmd_vel_pub = node.create_publisher(Twist, "/cmd_vel", 10)
        self._goal_pub = node.create_publisher(PoseStamped, "/goal_pose", 10)
        node.create_subscription(Odometry, "/odometry_map", self._odom_cb, 10)
        node.create_subscription(Float32, "owon/value", self._voltage_cb, 10)

        _camera_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE,
        )
        node.create_subscription(
            CompressedImage,
            "camera/frontleft_fisheye/image/compressed",
            self._camera_cb,
            _camera_qos,
        )

        self._spin_thread = threading.Thread(
            target=rclpy.spin,
            args=(node,),
            daemon=True,
        )
        self._spin_thread.start()
        print("[ros_bridge] started — node /web_bridge spinning")

    def stop(self) -> None:
        if not _ROS_AVAILABLE:
            return
        try:
            rclpy.shutdown()
        except Exception:
            pass
        if self._spin_thread is not None:
            self._spin_thread.join(timeout=3)

    def publish_cmd_vel(self, vx: float, vy: float, omega: float) -> None:
        if self._cmd_vel_pub is None:
            return
        msg = Twist(
            linear=Vector3(x=float(vx), y=float(vy), z=0.0),
            angular=Vector3(x=0.0, y=0.0, z=float(omega)),
        )
        self._cmd_vel_pub.publish(msg)

    def publish_zero_vel(self) -> None:
        self.publish_cmd_vel(0.0, 0.0, 0.0)

    def publish_goal(self, x: float, y: float, yaw: float) -> None:
        if self._goal_pub is None:
            return
        msg = PoseStamped()
        msg.header.frame_id = "map"
        msg.pose.position.x = float(x)
        msg.pose.position.y = float(y)
        msg.pose.position.z = 0.0
        half = yaw / 2.0
        msg.pose.orientation = Quaternion(
            x=0.0, y=0.0, z=math.sin(half), w=math.cos(half)
        )
        self._goal_pub.publish(msg)

    def get_state(self) -> dict | None:
        with self._lock:
            return dict(self._latest_odom) if self._latest_odom else None

    def get_voltage(self) -> dict | None:
        with self._lock:
            reading = dict(self._latest_voltage) if self._latest_voltage else None
        if reading is None:
            return None
        reading["stale"] = (time.time() - reading["timestamp"]) > VOLTAGE_STALE_AFTER_SEC
        return reading

    def _voltage_cb(self, msg: Any) -> None:
        with self._lock:
            self._latest_voltage = {
                "value": msg.data,
                "unit": "V",
                "timestamp": time.time(),
            }

    def _camera_cb(self, msg: Any) -> None:
        data = bytes(msg.data)
        with self._lock:
            self._latest_frame = data
            self._frame_seq += 1

    def get_latest_frame(self) -> tuple[int, bytes] | None:
        with self._lock:
            if self._latest_frame is None:
                return None
            return (self._frame_seq, self._latest_frame)

    def _start_mock_voltage(self) -> None:
        """Dev-only stand-in for the owon/value topic when rclpy/hardware isn't
        present (e.g. developing on a laptop instead of the robot's onboard
        compute). Enabled via MOCK_VOLTAGE=1; never runs when ROS is available."""
        import random

        def _loop() -> None:
            while True:
                with self._lock:
                    self._latest_voltage = {
                        "value": round(random.uniform(40.0, 48.0), 2),
                        "unit": "V",
                        "timestamp": time.time(),
                    }
                time.sleep(1.0)

        threading.Thread(target=_loop, daemon=True).start()
        print("[ros_bridge] MOCK_VOLTAGE=1 — publishing synthetic voltage readings for local UI testing")

    def _odom_cb(self, msg: Any) -> None:
        pos = msg.pose.pose.position
        yaw = _yaw_from_quaternion(msg.pose.pose.orientation)
        with self._lock:
            self._latest_odom = {
                "x": pos.x,
                "y": pos.y,
                "z": pos.z,
                "yaw": yaw,
            }

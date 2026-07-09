from __future__ import annotations

import math
import os
import threading
from typing import Any

# rclpy and message types are imported lazily so the module can be imported
# even if ROS2 is not sourced (the server will degrade gracefully).
try:
    import rclpy
    from geometry_msgs.msg import PoseStamped, Quaternion
    from geometry_msgs.msg import Twist, Vector3
    from nav_msgs.msg import Odometry
    _ROS_AVAILABLE = True
except ImportError:
    _ROS_AVAILABLE = False


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
        self._spin_thread: threading.Thread | None = None
        self.available = _ROS_AVAILABLE

    def start(self) -> None:
        if not _ROS_AVAILABLE:
            print("[ros_bridge] rclpy not available — ROS bridge disabled")
            return

        os.environ.setdefault("RMW_IMPLEMENTATION", "rmw_zenoh_cpp")

        rclpy.init()
        node = rclpy.create_node("web_bridge")
        self._node = node

        self._cmd_vel_pub = node.create_publisher(Twist, "/cmd_vel", 10)
        self._goal_pub = node.create_publisher(PoseStamped, "/goal_pose", 10)
        node.create_subscription(Odometry, "/odometry_map", self._odom_cb, 10)

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

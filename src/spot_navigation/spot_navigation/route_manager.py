#!/usr/bin/env python3

from __future__ import annotations

import json
import math
from dataclasses import dataclass

import rclpy
from geometry_msgs.msg import Point, PoseStamped, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Bool
from visualization_msgs.msg import Marker, MarkerArray


@dataclass(frozen=True)
class Waypoint:
    name: str
    x: float
    y: float
    z: float = 0.0
    yaw: float = 0.0


@dataclass(frozen=True)
class Route:
    name: str
    pre_loop: tuple[Waypoint, ...] = ()
    loop: tuple[Waypoint, ...] = ()
    loop_forever: bool = False

    @property
    def waypoints(self) -> tuple[Waypoint, ...]:
        return self.pre_loop + self.loop


INITIAL_WAYPOINT = Waypoint("initial", 2.31596, 1.97848, 0.0, 0.00125396)
MIDPOINT_APPROACH_WAYPOINT = Waypoint(
    "midpoint_approach", 7.06736, 2.49701, 0.0, 0.521781
)
MIDPOINT_WAYPOINT = Waypoint("midpoint", 14.9858, -2.3239, 0.0, -1.56208)
MIDPOINT_EXIT_WAYPOINT = Waypoint(
    "midpoint_exit", 7.68595, -6.02727, 0.0, -3.11477
)
RETURN_WAYPOINT = Waypoint("return", -1.10975, -3.26786, 0.0, 1.61665)

ROUTES = {
    "initial": Route("initial", pre_loop=(INITIAL_WAYPOINT,)),
    "midpoint": Route(
        "midpoint",
        pre_loop=(
            MIDPOINT_APPROACH_WAYPOINT,
            MIDPOINT_WAYPOINT,
            MIDPOINT_EXIT_WAYPOINT,
            RETURN_WAYPOINT,
            INITIAL_WAYPOINT,
        ),
    ),
}


class RouteManager(Node):
    def __init__(self) -> None:
        super().__init__("route_manager")

        # ── Step 1: determine route source ────────────────────────────────
        self.declare_parameter("route_file", "")
        self.declare_parameter("route_name", "midpoint")
        route_file = str(self.get_parameter("route_file").value)
        route_name = str(self.get_parameter("route_name").value)

        if route_file:
            _parsed = self._parse_route_file(route_file)
            loop_forever_default = False
        else:
            self.route = self._select_route(route_name)
            loop_forever_default = self.route.loop_forever

        # ── Step 2: declare remaining parameters ──────────────────────────
        self.declare_parameter("odom_topic", "/odometry_map")
        self.declare_parameter("goal_topic", "/goal_pose")
        self.declare_parameter("marker_topic", "/goal_markers")
        self.declare_parameter("reach_status_topic", "/far_reach_goal_status")
        self.declare_parameter("frame_id", "map")
        self.declare_parameter("reach_status_ignore_sec", 0.5)
        self.declare_parameter("goal_republish_period", 2.0)
        self.declare_parameter("start_delay_sec", 2.0)
        self.declare_parameter("loop_forever", loop_forever_default)
        self.declare_parameter("initial_pose_settle_sec", 3.0)

        # ── Step 3: read parameter values ─────────────────────────────────
        odom_topic = str(self.get_parameter("odom_topic").value)
        goal_topic = str(self.get_parameter("goal_topic").value)
        marker_topic = str(self.get_parameter("marker_topic").value)
        reach_status_topic = str(self.get_parameter("reach_status_topic").value)
        self.frame_id = str(self.get_parameter("frame_id").value)
        self.reach_status_ignore_sec = float(
            self.get_parameter("reach_status_ignore_sec").value
        )
        self.goal_republish_period = float(
            self.get_parameter("goal_republish_period").value
        )
        self.start_delay_sec = float(self.get_parameter("start_delay_sec").value)
        self.loop_forever = bool(self.get_parameter("loop_forever").value)
        self.initial_pose_settle_sec = float(
            self.get_parameter("initial_pose_settle_sec").value
        )

        # ── Step 4: build route points ────────────────────────────────────
        if route_file:
            self.route_points = _parsed["waypoints"]
            self.loop_start_index = 0
            self._has_loop_segment = False
            self._initial_pose_msg = self._build_initialpose_msg(
                _parsed.get("initial_pose"), self.frame_id
            )
            route_label = f"file:{route_file}"
        else:
            self.route_points = list(self.route.waypoints)
            self.loop_start_index = len(self.route.pre_loop)
            self._has_loop_segment = bool(self.route.loop)
            self._initial_pose_msg = None
            route_label = self.route.name

        if not self.route_points:
            raise RuntimeError("Route has no waypoints")

        # ── Step 5: publishers and subscribers ────────────────────────────
        self.goal_pub = self.create_publisher(PoseStamped, goal_topic, 10)
        self.marker_pub = self.create_publisher(MarkerArray, marker_topic, 1)
        self.initialpose_pub = self.create_publisher(
            PoseWithCovarianceStamped, "/initialpose", 1
        )
        self.create_subscription(Odometry, odom_topic, self._odom_callback, 10)
        self.create_subscription(
            Bool, reach_status_topic, self._reach_status_callback, 10
        )

        self.current_pose = None
        self.active_index = 0
        self.active_goal: Waypoint | None = None
        self.far_status_armed = False
        self.far_goal_reached = False
        self.active_goal_start_time = None
        self.route_started = False
        self.last_publish_time = None
        self.start_time = self.get_clock().now()
        self._initial_pose_published_at = None

        self.create_timer(0.2, self._tick)
        self.create_timer(1.0, self._publish_route_markers)

        self.get_logger().info(
            f"Route manager loaded '{route_label}' with "
            f"{len(self.route_points)} waypoints"
        )

    # ── Static helpers ────────────────────────────────────────────────────

    @staticmethod
    def _parse_route_file(path: str) -> dict:
        with open(path) as f:
            data = json.load(f)
        waypoints = [
            Waypoint(
                name=g.get("name", f"goal_{i + 1}"),
                x=float(g["x"]),
                y=float(g["y"]),
                z=float(g.get("z", 0.0)),
                yaw=float(g.get("yaw", 0.0)),
            )
            for i, g in enumerate(data["goals"])
        ]
        return {"waypoints": waypoints, "initial_pose": data.get("initial_pose")}

    @staticmethod
    def _build_initialpose_msg(
        ip: dict | None, frame_id: str
    ) -> PoseWithCovarianceStamped | None:
        if ip is None:
            return None
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = frame_id
        yaw = float(ip.get("yaw", 0.0))
        msg.pose.pose.position.x = float(ip["x"])
        msg.pose.pose.position.y = float(ip["y"])
        msg.pose.pose.position.z = float(ip.get("z", 0.0))
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        msg.pose.covariance[0] = 0.25    # σ²_x
        msg.pose.covariance[7] = 0.25    # σ²_y
        msg.pose.covariance[35] = 0.0685  # σ²_yaw
        return msg

    # ── Legacy route selection ────────────────────────────────────────────

    def _select_route(self, route_name: str) -> Route:
        if route_name not in ROUTES:
            valid_routes = ", ".join(sorted(ROUTES))
            raise RuntimeError(
                f"Unknown route_name '{route_name}'. Valid routes: {valid_routes}"
            )
        return ROUTES[route_name]

    # ── ROS callbacks ─────────────────────────────────────────────────────

    def _odom_callback(self, msg: Odometry) -> None:
        self.current_pose = msg.pose.pose

    def _reach_status_callback(self, msg: Bool) -> None:
        if self.active_goal is None:
            return

        if not msg.data:
            self.far_status_armed = True
            self.far_goal_reached = False
            return

        if (
            self.far_status_armed
            or self._active_goal_age() >= self.reach_status_ignore_sec
        ):
            self.far_goal_reached = True

    # ── State machine ─────────────────────────────────────────────────────

    def _tick(self) -> None:
        if self.current_pose is None:
            return

        elapsed = (self.get_clock().now() - self.start_time).nanoseconds / 1e9
        if not self.route_started and elapsed < self.start_delay_sec:
            return
        self.route_started = True

        if self._initial_pose_published_at is not None:
            settle_elapsed = (
                self.get_clock().now() - self._initial_pose_published_at
            ).nanoseconds / 1e9
            if settle_elapsed < self.initial_pose_settle_sec:
                return

        if self.active_goal is None:
            self._start_current_goal()
            return

        if self._active_goal_reached():
            self.get_logger().info(
                f"Reached waypoint {self.active_goal.name} "
                f"({self.active_index + 1}/{len(self.route_points)})"
            )
            next_goal = self._advance_goal()
            if next_goal is None:
                self.get_logger().info("Route complete; no more waypoints to publish")
                self.active_goal = None
                self._publish_route_markers()
                return
            self.active_goal = next_goal
            self._reset_reach_status()
            self._publish_active_goal(force=True)
            self._publish_route_markers()
            return

        self._publish_active_goal(force=False)

    def _start_current_goal(self) -> None:
        if self._initial_pose_msg is not None:
            self._initial_pose_msg.header.stamp = self.get_clock().now().to_msg()
            self.initialpose_pub.publish(self._initial_pose_msg)
            self.get_logger().info(
                f"Published initial pose to /initialpose; "
                f"waiting {self.initial_pose_settle_sec:.1f}s for localization to settle"
            )
            self._initial_pose_published_at = self.get_clock().now()
            self._initial_pose_msg = None
            return  # _tick will hold until settle window passes

        self.active_goal = self._current_waypoint()
        if self.active_goal is None:
            return
        self._reset_reach_status()
        self._publish_active_goal(force=True)
        self._publish_route_markers()

    def _current_waypoint(self) -> Waypoint | None:
        if 0 <= self.active_index < len(self.route_points):
            return self.route_points[self.active_index]
        return self._restart_loop_if_needed()

    def _advance_goal(self) -> Waypoint | None:
        self.active_index += 1
        if self.active_index < len(self.route_points):
            return self.route_points[self.active_index]

        return self._restart_loop_if_needed()

    def _restart_loop_if_needed(self) -> Waypoint | None:
        if not self.loop_forever or not self._has_loop_segment:
            return None
        self.active_index = self.loop_start_index
        return self.route_points[self.active_index]

    def _active_goal_reached(self) -> bool:
        return self.active_goal is not None and self.far_goal_reached

    def _reset_reach_status(self) -> None:
        self.far_status_armed = False
        self.far_goal_reached = False
        self.active_goal_start_time = self.get_clock().now()

    def _active_goal_age(self) -> float:
        if self.active_goal_start_time is None:
            return 0.0
        return (self.get_clock().now() - self.active_goal_start_time).nanoseconds / 1e9

    def _publish_active_goal(self, force: bool) -> None:
        if self.active_goal is None:
            return

        now = self.get_clock().now()
        if not force and self.last_publish_time is not None:
            dt = (now - self.last_publish_time).nanoseconds / 1e9
            if dt < self.goal_republish_period:
                return

        msg = PoseStamped()
        msg.header.frame_id = self.frame_id
        msg.header.stamp = now.to_msg()
        msg.pose.position.x = self.active_goal.x
        msg.pose.position.y = self.active_goal.y
        msg.pose.position.z = self.active_goal.z
        msg.pose.orientation.z = math.sin(self.active_goal.yaw / 2.0)
        msg.pose.orientation.w = math.cos(self.active_goal.yaw / 2.0)

        self.goal_pub.publish(msg)
        self.last_publish_time = now
        self.get_logger().info(
            f"Published waypoint {self.active_goal.name}: "
            f"x={msg.pose.position.x:.3f}, "
            f"y={msg.pose.position.y:.3f}, "
            f"yaw={self.active_goal.yaw:.3f}"
        )

    def _all_waypoints(self) -> list[Waypoint]:
        return self.route_points

    def _publish_route_markers(self) -> None:
        now = self.get_clock().now().to_msg()
        markers = MarkerArray()

        delete_marker = Marker()
        delete_marker.action = Marker.DELETEALL
        markers.markers.append(delete_marker)

        route_points = self._all_waypoints()
        if route_points:
            line = Marker()
            line.header.frame_id = self.frame_id
            line.header.stamp = now
            line.ns = "route_manager"
            line.id = 0
            line.type = Marker.LINE_STRIP
            line.action = Marker.ADD
            line.scale.x = 0.06
            line.color.r = 0.1
            line.color.g = 0.4
            line.color.b = 1.0
            line.color.a = 0.8
            for waypoint in route_points:
                point = Point()
                point.x = waypoint.x
                point.y = waypoint.y
                point.z = waypoint.z + 0.2
                line.points.append(point)
            markers.markers.append(line)

        active_name = self.active_goal.name if self.active_goal is not None else ""
        for marker_index, waypoint in enumerate(route_points, start=1):
            sphere = Marker()
            sphere.header.frame_id = self.frame_id
            sphere.header.stamp = now
            sphere.ns = "route_manager_goals"
            sphere.id = marker_index
            sphere.type = Marker.SPHERE
            sphere.action = Marker.ADD
            sphere.pose.position.x = waypoint.x
            sphere.pose.position.y = waypoint.y
            sphere.pose.position.z = waypoint.z + 0.25
            sphere.scale.x = 0.35
            sphere.scale.y = 0.35
            sphere.scale.z = 0.35
            if waypoint.name == active_name:
                sphere.color.r = 0.0
                sphere.color.g = 1.0
                sphere.color.b = 0.2
            else:
                sphere.color.r = 0.1
                sphere.color.g = 0.4
                sphere.color.b = 1.0
            sphere.color.a = 0.9
            markers.markers.append(sphere)

            text = Marker()
            text.header.frame_id = self.frame_id
            text.header.stamp = now
            text.ns = "route_manager_labels"
            text.id = marker_index + 1000
            text.type = Marker.TEXT_VIEW_FACING
            text.action = Marker.ADD
            text.pose.position.x = waypoint.x
            text.pose.position.y = waypoint.y
            text.pose.position.z = waypoint.z + 0.75
            text.scale.z = 0.35
            text.color.r = 1.0
            text.color.g = 1.0
            text.color.b = 1.0
            text.color.a = 0.95
            text.text = waypoint.name
            markers.markers.append(text)

        self.marker_pub.publish(markers)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RouteManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("ws_host", default_value="0.0.0.0",
                              description="WebSocket server bind address"),
        DeclareLaunchArgument("ws_port", default_value="8765",
                              description="WebSocket server port"),
        DeclareLaunchArgument("target_points", default_value="4000",
                              description="Max points per streamed frame after downsampling"),
        DeclareLaunchArgument("input_topic", default_value="/velodyne_points",
                              description="PointCloud2 topic to subscribe to"),
        DeclareLaunchArgument("publish_rate_hz", default_value="10.0",
                              description="Max frame rate to stream to clients"),
        Node(
            package="lidar_web_bridge",
            executable="lidar_stream",
            name="lidar_stream",
            output="screen",
            parameters=[{
                "ws_host": LaunchConfiguration("ws_host"),
                "ws_port": LaunchConfiguration("ws_port"),
                "target_points": LaunchConfiguration("target_points"),
                "input_topic": LaunchConfiguration("input_topic"),
                "publish_rate_hz": LaunchConfiguration("publish_rate_hz"),
            }],
        ),
    ])

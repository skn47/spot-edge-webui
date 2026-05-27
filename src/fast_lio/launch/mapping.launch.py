from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    package_path = get_package_share_directory("fast_lio")

    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time",
        default_value="false",
        description="Use simulation (bag) time if true",
    )

    config_file_arg = DeclareLaunchArgument(
        "config_file",
        default_value="velodyne_vlp16.yaml",
        description="Config file name (in fast_lio/config folder)",
    )

    map_file_path_arg = DeclareLaunchArgument(
        "map_file_path",
        default_value="scans.pcd",
        description="Output PCD filename (saved to fast_lio/pcd/)",
    )

    max_range_arg = DeclareLaunchArgument(
        "max_range",
        default_value="1000.0",
        description="Max point range in meters (preprocess filter)",
    )

    rviz_arg = DeclareLaunchArgument(
        "rviz", default_value="true", description="Start RViz"
    )

    config_path = PathJoinSubstitution(
        [package_path, "config", LaunchConfiguration("config_file")]
    )

    fast_lio_node = Node(
        package="fast_lio",
        executable="fastlio_mapping",
        output="screen",
        parameters=[
            config_path,
            {
                "use_sim_time": LaunchConfiguration("use_sim_time"),
                "publish.map_en": True,
                # Offline bag replay: denser settings for better map quality
                "filter_size_surf": 0.3,       # scan downsample voxel (default 0.5)
                "filter_size_map": 0.3,         # map voxel resolution (default 0.5)
                "point_filter_num": 1,          # keep all points (default 2 = every 2nd)
                "map_file_path": LaunchConfiguration("map_file_path"),
                "preprocess.max_range": LaunchConfiguration("max_range"),
            },
        ],
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        arguments=[
            "-d",
            PathJoinSubstitution([package_path, "rviz", "fastlio.rviz"]),
        ],
        parameters=[{"use_sim_time": LaunchConfiguration("use_sim_time")}],
        condition=IfCondition(LaunchConfiguration("rviz")),
    )

    return LaunchDescription(
        [
            use_sim_time_arg,
            config_file_arg,
            map_file_path_arg,
            max_range_arg,
            rviz_arg,
            fast_lio_node,
            rviz_node,
        ]
    )

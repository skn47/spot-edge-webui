import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    package_name = "fast_lio"

    # Arguments
    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time",
        default_value="false",
        description="Use simulation (bag) time if true",
    )

    map_path_arg = DeclareLaunchArgument(
        "map_path",
        default_value=os.path.join(
            get_package_share_directory(package_name),
            "pcd",
            "mine_map3_final_clean.pcd",
        ),
        description="Path to the global PCD map file",
    )

    publish_goals_arg = DeclareLaunchArgument(
        "publish_goals",
        default_value="false",
        description="Whether to publish goal markers from goals.yaml",
    )

    config_file_arg = DeclareLaunchArgument(
        "config_file",
        default_value="velodyne_vlp16.yaml",
        description="FAST-LIO config file name (must be in config folder)",
    )

    # FAST-LIO config path
    fast_lio_config_path = PathJoinSubstitution(
        [
            get_package_share_directory(package_name),
            "config",
            LaunchConfiguration("config_file"),
        ]
    )

    # 1. Terrain Processor
    # Handles ground/ceiling filtering and publishes static map topics
    terrain_processor_node = Node(
        package="terrain_analysis",
        executable="terrain_processor",
        name="terrain_processor",
        output="screen",
        parameters=[
            fast_lio_config_path,
            {
                "map_path": LaunchConfiguration("map_path"),
                "use_sim_time": LaunchConfiguration("use_sim_time"),
            },
        ],
        remappings=[("/scan_cloud", "/cloud_registered_body")],
    )

    # 2. FAST-LIO
    fast_lio_node = Node(
        package=package_name,
        executable="fastlio_mapping",
        name="fast_lio",
        output="screen",
        parameters=[
            fast_lio_config_path,
            {
                "use_sim_time": LaunchConfiguration("use_sim_time"),
                # Overrides for Localization Mode
                "publish.map_en": False,
                "pcd_save.pcd_save_en": False,
                "mapping.extrinsic_est_en": False,
                "publish.scan_publish_en": True,
                "publish.scan_bodyframe_pub_en": True,
                "publish.dense_publish_en": False,
            },
        ],
        remappings=[("/Odometry", "/odometry_lio")],
    )

    # 3. Localization Node
    # Subscribes to global_map published by terrain_processor
    localization_node = Node(
        package=package_name,
        executable="fast_lio_localization_node",
        name="ndt_localization",
        output="screen",
        parameters=[
            fast_lio_config_path,
            {
                "use_sim_time": LaunchConfiguration("use_sim_time"),
            },
        ],
    )

    # 4. Goal Publisher (Optional)
    from launch.conditions import IfCondition

    goal_publisher_node = Node(
        package=package_name,
        executable="publish_goals.py",
        name="goal_publisher",
        output="screen",
        condition=IfCondition(LaunchConfiguration("publish_goals")),
        parameters=[{"use_sim_time": LaunchConfiguration("use_sim_time")}],
    )

    # RViz
    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="screen",
        arguments=[
            "-d",
            PathJoinSubstitution(
                [get_package_share_directory(package_name), "rviz", "localization.rviz"]
            ),
        ],
        parameters=[{"use_sim_time": LaunchConfiguration("use_sim_time")}],
    )

    return LaunchDescription(
        [
            map_path_arg,
            use_sim_time_arg,
            publish_goals_arg,
            config_file_arg,
            terrain_processor_node,
            fast_lio_node,
            localization_node,
            goal_publisher_node,
            rviz_node,
        ]
    )

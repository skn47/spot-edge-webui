import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, SetParameter

def generate_launch_description():
    package_name = 'far_planner'

    # --- Arguments ---
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', 
        default_value='false',
        description='Use simulation time'
    )

    config_file_arg = DeclareLaunchArgument(
        'config_file', 
        default_value='default.yaml',
        description='FAR Planner config file name (must be in config folder)'
    )

    # Config Path
    far_planner_config_path = PathJoinSubstitution([
        get_package_share_directory(package_name),
        'config',
        LaunchConfiguration('config_file')
    ])

    # FAR Planner Node
    far_planner_node = Node(
        package=package_name,
        executable='far_planner',
        name='far_planner',
        output='screen',
        parameters=[
            far_planner_config_path,
            {'use_sim_time': LaunchConfiguration('use_sim_time')}
        ],
        remappings=[
            # 1. Odometry: Connect FAR to FAST-LIO's global odometry
            ('/odom_world', '/odometry_map'),
            # 2. Global Mapping Input:
            # We keep this as the LIO-registered cloud. It is drift-corrected and ideal 
            # for building the consistent global visibility graph.
            # ('/terrain_cloud', '/cloud_registered'), 

            # 3. Dynamic Obstacle Detection Input:
            # We use the RAW cloud here as requested. This allows FAR to see 
            # obstacles that LIO might have filtered out.
            # FAR Planner will transform this to world frame using TF.
            # ('/scan_cloud', '/velodyne_points'),

            # 4. Local Clearance Check Input:
            # Uses the body-frame registered cloud for immediate collision checking.
            ('/terrain_local_cloud', '/terrain_cloud'),

            # 5. Output:
            # This topic (/way_point) needs to be consumed by your local controller.
            # ('/way_point', '/goal_manager/target_point') 
        ]
    )

    # Graph Decoder (Optional helper node)
    # graph_decoder_launch = IncludeLaunchDescription(
    #     PythonLaunchDescriptionSource([
    #         get_package_share_directory('graph_decoder'), 
    #         '/launch/decoder.launch.py'
    #     ])
    # )

    # RViz (Optional)
    # rviz_node = Node(
    #     package='rviz2',
    #     executable='rviz2',
    #     name='rviz2',
    #     output='screen',
    #     arguments=['-d', PathJoinSubstitution([
    #         get_package_share_directory(package_name), 
    #         'rviz', 
    #         'default.rviz'
    #     ])],
    #     parameters=[{'use_sim_time': LaunchConfiguration('use_sim_time')}]
    # )

    return LaunchDescription([
        # Sets use_sim_time for all nodes that don't explicitly override it, 
        # though passing it explicitly in parameters is also good practice.
        SetParameter(name='use_sim_time', value=LaunchConfiguration('use_sim_time')),
        
        use_sim_time_arg,
        config_file_arg,
        far_planner_node,
        # graph_decoder_launch,
        # rviz_node
    ])

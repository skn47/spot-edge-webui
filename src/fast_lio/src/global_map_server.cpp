#include "global_map_server.h"

namespace fast_lio
{

GlobalMapServer::GlobalMapServer() : Node("global_map_server_node")
{
  RCLCPP_INFO(this->get_logger(), "Initializing Global Map Server Node");

  // Parameters
  this->declare_parameter<std::string>("map_path", "");
  this->declare_parameter<std::string>("global_map.map_frame_id", "camera_init");
  this->declare_parameter<double>("global_map.map_leaf_size", 0.1);
  
  // PMF Parameters
  this->declare_parameter<bool>("global_map.use_pmf", true);
  // TODO: tune these defaults later
  this->declare_parameter<double>("global_map.pmf_max_window_size", 6.0);
  this->declare_parameter<double>("global_map.pmf_slope", 2.5);
  this->declare_parameter<double>("global_map.pmf_initial_distance", 0.8);
  this->declare_parameter<double>("global_map.pmf_max_distance", 1.0);

  this->get_parameter("map_path", this->map_path_);
  this->get_parameter("global_map.map_frame_id", this->map_frame_id_);
  this->get_parameter("global_map.map_leaf_size", this->map_leaf_size_);
  this->get_parameter("global_map.use_pmf", this->use_pmf_);
  
  this->get_parameter("global_map.pmf_max_window_size", this->pmf_max_window_size_);
  this->get_parameter("global_map.pmf_slope", this->pmf_slope_);
  this->get_parameter("global_map.pmf_initial_distance", this->pmf_initial_distance_);
  this->get_parameter("global_map.pmf_max_distance", this->pmf_max_distance_);

  // Publisher (Latched)
  rclcpp::QoS qos_profile(1);
  qos_profile.transient_local();
  this->pub_global_map_ = this->create_publisher<sensor_msgs::msg::PointCloud2>("global_map", qos_profile);

  this->global_map_cloud_.reset(new pcl::PointCloud<PointType>());
}

GlobalMapServer::~GlobalMapServer() {}

void GlobalMapServer::start()
{
  this->loadAndFilterMap();
}

void GlobalMapServer::loadAndFilterMap()
{
  if (this->map_path_.empty()) {
    RCLCPP_WARN(this->get_logger(), "No map path specified.");
    return;
  }

  RCLCPP_INFO(this->get_logger(), "Loading map from: %s", this->map_path_.c_str());

  // Load as PointXYZ first (since the file might not have intensity)
  pcl::PointCloud<pcl::PointXYZ>::Ptr raw_map_xyz(new pcl::PointCloud<pcl::PointXYZ>());

  if (pcl::io::loadPCDFile<pcl::PointXYZ>(this->map_path_, *raw_map_xyz) == -1) {
    RCLCPP_ERROR(this->get_logger(), "Failed to load PCD file.");
    return;
  }
  RCLCPP_INFO(this->get_logger(), "Loaded %zu points (XYZ only).", raw_map_xyz->size());

  // Convert to PointXYZI
  pcl::PointCloud<PointType>::Ptr raw_map(new pcl::PointCloud<PointType>());
  raw_map->points.resize(raw_map_xyz->size());
  for (size_t i = 0; i < raw_map_xyz->size(); i++) {
    raw_map->points[i].x = raw_map_xyz->points[i].x;
    raw_map->points[i].y = raw_map_xyz->points[i].y;
    raw_map->points[i].z = raw_map_xyz->points[i].z;
    raw_map->points[i].intensity = 0.0f; // Default intensity
  }
  raw_map->width = raw_map_xyz->width;
  raw_map->height = raw_map_xyz->height;
  raw_map->is_dense = raw_map_xyz->is_dense;

  // 1. Voxel Grid Filter
  pcl::PointCloud<PointType>::Ptr downsampled_map(new pcl::PointCloud<PointType>());
  if (this->map_leaf_size_ > 0.0) {
    RCLCPP_INFO(this->get_logger(), "Downsampling map (leaf size: %.2f)...", this->map_leaf_size_);
    pcl::VoxelGrid<PointType> voxel_grid;
    voxel_grid.setLeafSize(this->map_leaf_size_, this->map_leaf_size_, this->map_leaf_size_);
    voxel_grid.setInputCloud(raw_map);
    voxel_grid.filter(*downsampled_map);
  } else {
    downsampled_map = raw_map;
  }
  RCLCPP_INFO(this->get_logger(), "Map size after downsampling: %zu", downsampled_map->size());

  // 2. Ground Segmentation (PMF)
  if (this->use_pmf_) {
    RCLCPP_INFO(this->get_logger(), "Applying PMF Ground Segmentation...");
    pcl::PointIndices::Ptr ground_indices(new pcl::PointIndices);
    pcl::ApproximateProgressiveMorphologicalFilter<PointType> pmf;
    pmf.setInputCloud(downsampled_map);
    pmf.setMaxWindowSize(this->pmf_max_window_size_);
    pmf.setSlope(this->pmf_slope_);
    pmf.setInitialDistance(this->pmf_initial_distance_);
    pmf.setMaxDistance(this->pmf_max_distance_);
    pmf.extract(ground_indices->indices);

    RCLCPP_INFO(this->get_logger(), "PMF complete. Found %zu ground points.", ground_indices->indices.size());

    // Mark intensities
    // Default all to 1.0 (Obstacle)
    for (auto& pt : downsampled_map->points) {
      pt.intensity = 1.0f;
    }

    // Set Ground indices to 0.0
    for (int index : ground_indices->indices) {
      downsampled_map->points[index].intensity = 0.0f;
    }

    // Ceiling Segmentation (Inverted PMF)
    // To handle sloping tunnels, we flip the world upside down and run PMF again.
    // The "ground" of the upside-down world is the "ceiling" of the real world.
    
    RCLCPP_INFO(this->get_logger(), "Applying Inverted PMF for Ceiling Segmentation...");
    
    pcl::PointCloud<PointType>::Ptr inverted_map(new pcl::PointCloud<PointType>());
    *inverted_map = *downsampled_map;
    
    // Invert Z coordinates
    for (auto& pt : inverted_map->points) {
        pt.z = -pt.z;
    }

    pcl::PointIndices::Ptr ceiling_indices(new pcl::PointIndices);
    pcl::ApproximateProgressiveMorphologicalFilter<PointType> pmf_ceiling;
    pmf_ceiling.setInputCloud(inverted_map);
    // We use the same parameters as ground, or maybe slightly relaxed
    pmf_ceiling.setMaxWindowSize(this->pmf_max_window_size_);
    pmf_ceiling.setSlope(this->pmf_slope_);
    pmf_ceiling.setInitialDistance(this->pmf_initial_distance_);
    pmf_ceiling.setMaxDistance(this->pmf_max_distance_); // Max distance from the "surface" (ceiling)
    pmf_ceiling.extract(ceiling_indices->indices);

    RCLCPP_INFO(this->get_logger(), "Ceiling PMF complete. Found %zu ceiling points.", ceiling_indices->indices.size());

    // Mark ceiling points as safe (0.0)
    for (int index : ceiling_indices->indices) {
      downsampled_map->points[index].intensity = 0.0f;
    }
    // ---------------------------------------------------------

  } else {
    // If no PMF, assume everything is obstacle? or keep original intensity?
    // Let's set everything to 1.0 (Obstacle) to be safe for planning
    RCLCPP_INFO(this->get_logger(), "PMF disabled. Marking all points as obstacles (intensity = 1.0).");
    for (auto& pt : downsampled_map->points) {
      pt.intensity = 1.0f;
    }
  }

  this->global_map_cloud_ = downsampled_map;

  // 3. Publish
  sensor_msgs::msg::PointCloud2 output_msg;
  pcl::toROSMsg(*this->global_map_cloud_, output_msg);
  output_msg.header.frame_id = this->map_frame_id_;
  output_msg.header.stamp = this->now();
  
  this->pub_global_map_->publish(output_msg);
  RCLCPP_INFO(this->get_logger(), "Published global map.");
}

} // namespace fast_lio

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<fast_lio::GlobalMapServer>();
  node->start();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}

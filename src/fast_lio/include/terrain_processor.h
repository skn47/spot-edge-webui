#pragma once

#include <mutex>
#include <memory>
#include <string>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/point_cloud2.hpp"

#include <pcl/point_cloud.h>
#include <pcl/point_types.h>
#include <pcl_conversions/pcl_conversions.h>
#include <pcl/io/pcd_io.h>
#include <pcl/filters/voxel_grid.h>
#include <pcl/filters/extract_indices.h>
#include <pcl/segmentation/approximate_progressive_morphological_filter.h>

// Define the point type
using PointType = pcl::PointXYZI;

namespace fast_lio
{
class TerrainProcessor : public rclcpp::Node
{
public:
  TerrainProcessor();
  ~TerrainProcessor();

  void start();

private:
  void loadAndFilterMap();

  // Parameters
  std::string map_path_;
  std::string map_frame_id_;
  double map_leaf_size_;
  bool use_pmf_; 

  // PMF Parameters
  double pmf_max_window_size_;
  double pmf_slope_;
  double pmf_initial_distance_;
  double pmf_max_distance_;

  // Publisher
  // Publishes the full map (with ceiling) for visualization or general use
  rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr pub_global_map_;

  // Publishes the map with CEILING REMOVED for far_planner
  rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr pub_global_map_planning_;

  // Data
  pcl::PointCloud<PointType>::Ptr global_map_cloud_;
};
} // namespace fast_lio

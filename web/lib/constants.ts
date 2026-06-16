export const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ?? "ws://192.168.1.150:8765";

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://192.168.1.150:8000";

export const BACKEND_WS_URL =
  process.env.NEXT_PUBLIC_BACKEND_WS_URL ?? "ws://192.168.1.150:8000";

export const POINT_SIZE = 0.02;
export const POINT_COLOR = "#00ff88";

export const PROCESS_LABELS: Record<string, string> = {
  lidar_stream: "LiDAR stream",
  sensors: "Sensors",
  localization: "Localization",
  navigation: "Navigation",
  route_manager: "Route manager",
  rviz: "RViz2",
};

const _host =
  process.env.NEXT_PUBLIC_HOST ??
  (typeof window !== "undefined" ? window.location.hostname : "localhost");

export const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ?? `ws://${_host}:8765`;

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? `http://${_host}:8000`;

export const BACKEND_WS_URL =
  process.env.NEXT_PUBLIC_BACKEND_WS_URL ?? `ws://${_host}:8000`;

export const POINT_SIZE = 0.02;
export const POINT_COLOR = "#00ff88";

// Mirrors the defaults for voltage_warn_threshold / voltage_critical_threshold
// in owon_driver's owon_node.cpp, so the badge agrees with the RViz marker color.
export const VOLTAGE_WARN_THRESHOLD = 45.0;
export const VOLTAGE_CRITICAL_THRESHOLD = 42.0;

export const PROCESS_LABELS: Record<string, string> = {
  lidar_stream: "LiDAR stream",
  sensors: "Sensors",
  localization: "Localization",
  navigation: "Navigation",
  route_manager: "Route manager",
  rviz: "RViz2",
};

import { BACKEND_URL } from "./constants";

export interface ProcessResponse {
  ok: boolean;
  pid: number | null;
  message: string;
}

export interface MissionResponse {
  ok: boolean;
  action: string;
  message: string;
}

export interface ProcessStatus {
  running: boolean;
  pid: number | null;
  returncode: number | null;
}

export interface OdometryState {
  x: number;
  y: number;
  z: number;
  yaw: number;
}

export interface VoltageState {
  value: number;
  unit: string;
  timestamp: number;
  stale: boolean;
}

export interface RobotState {
  timestamp: number;
  odometry: OdometryState | null;
  voltage: VoltageState | null;
  mission_active: boolean;
  mission_paused: boolean;
  process_statuses: Record<string, ProcessStatus>;
}

export interface LogLine {
  source: string;
  stream: "stdout" | "stderr";
  text: string;
  timestamp: number;
}

export interface TopicInfo {
  label: string;
  exists: boolean;
  publishers: number;
  subscribers: number;
  ok: boolean;
  warning: string | null;
}

export interface DiagnosticResult {
  ok: boolean;
  checks: {
    zenoh_router: { ok: boolean; detail: string };
    nodes: { ok: boolean; found: string[]; missing: string[]; detail?: string };
    topics: Record<string, TopicInfo>;
  };
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export async function processAction(
  action: "start" | "stop" | "restart",
  scriptName: string,
  mapName?: string
): Promise<ProcessResponse> {
  return post<ProcessResponse>(`/api/process/${action}`, {
    script_name: scriptName,
    ...(mapName !== undefined && { map_name: mapName }),
  });
}

export async function missionStart(mapName: string): Promise<MissionResponse> {
  return post<MissionResponse>("/api/mission/start", { map_name: mapName });
}

export async function missionAction(
  action: "stop" | "pause" | "resume" | "home" | "estop"
): Promise<MissionResponse> {
  return post<MissionResponse>(`/api/mission/${action}`);
}

export async function fetchMaps(): Promise<string[]> {
  const res = await fetch(`${BACKEND_URL}/api/maps`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.maps ?? [];
}

export interface RouteUploadResponse {
  ok: boolean;
  filename: string;
  goal_count: number;
}

export async function uploadRoute(file: File): Promise<RouteUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BACKEND_URL}/api/route/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? res.statusText);
  }
  return res.json() as Promise<RouteUploadResponse>;
}

export async function setDriverCredentials(
  hostname: string,
  username: string,
  password: string
): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>("/api/driver/credentials", { hostname, username, password });
}

export async function clearRoute(): Promise<{ ok: boolean }> {
  const res = await fetch(`${BACKEND_URL}/api/route/clear`, { method: "POST" });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export async function runDiagnostic(): Promise<DiagnosticResult> {
  const res = await fetch(`${BACKEND_URL}/api/diagnostic`);
  if (!res.ok) throw new Error(`Diagnostic request failed: ${res.statusText}`);
  return res.json() as Promise<DiagnosticResult>;
}

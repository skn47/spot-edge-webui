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

export interface RobotState {
  timestamp: number;
  odometry: OdometryState | null;
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
  scriptName: string
): Promise<ProcessResponse> {
  return post<ProcessResponse>(`/api/process/${action}`, {
    script_name: scriptName,
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

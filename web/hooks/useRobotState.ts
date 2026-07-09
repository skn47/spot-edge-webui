"use client";

import { useEffect, useRef, useState } from "react";
import { RobotState } from "@/lib/api";
import { BACKEND_WS_URL } from "@/lib/constants";

export interface RobotStateHook {
  state: RobotState | null;
  connected: boolean;
}

const RECONNECT_BASE_MS = 2_000;
const RECONNECT_MAX_MS = 10_000;

export function useRobotState(): RobotStateHook {
  const [state, setState] = useState<RobotState | null>(null);
  const [connected, setConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const delayRef = useRef(RECONNECT_BASE_MS);

  useEffect(() => {
    let active = true;

    function connect() {
      if (!active) return;
      const ws = new WebSocket(`${BACKEND_WS_URL}/ws/state`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!active) return;
        delayRef.current = RECONNECT_BASE_MS;
        setConnected(true);
        console.log("[useRobotState] connected", `${BACKEND_WS_URL}/ws/state`);
      };

      ws.onmessage = (ev: MessageEvent<string>) => {
        if (!active || typeof ev.data !== "string") return;
        try {
          const parsed = JSON.parse(ev.data) as RobotState;
          console.log("[useRobotState] msg", parsed);
          setState(parsed);
        } catch (e) {
          console.warn("[useRobotState] parse error", e, ev.data);
        }
      };

      ws.onerror = (e) => {
        console.warn("[useRobotState] error", e);
        if (!active) return;
      };

      ws.onclose = (e) => {
        console.warn("[useRobotState] closed", { code: e.code, reason: e.reason, wasClean: e.wasClean });
        if (!active) return;
        setConnected(false);
        timerRef.current = setTimeout(() => {
          delayRef.current = Math.min(delayRef.current * 2, RECONNECT_MAX_MS);
          connect();
        }, delayRef.current);
      };
    }

    connect();

    return () => {
      active = false;
      if (timerRef.current !== null) clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, []);

  return { state, connected };
}

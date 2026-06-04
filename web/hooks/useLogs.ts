"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { LogLine } from "@/lib/api";
import { BACKEND_WS_URL } from "@/lib/constants";

export interface LogsHook {
  lines: LogLine[];
  connected: boolean;
  clear: () => void;
}

const MAX_LINES = 500;
const RECONNECT_BASE_MS = 2_000;
const RECONNECT_MAX_MS = 10_000;

export function useLogs(): LogsHook {
  const [lines, setLines] = useState<LogLine[]>([]);
  const [connected, setConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const delayRef = useRef(RECONNECT_BASE_MS);

  const clear = useCallback(() => setLines([]), []);

  useEffect(() => {
    let active = true;

    function connect() {
      if (!active) return;
      const ws = new WebSocket(`${BACKEND_WS_URL}/ws/logs`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!active) return;
        delayRef.current = RECONNECT_BASE_MS;
        setConnected(true);
        console.log("[useLogs] connected", `${BACKEND_WS_URL}/ws/logs`);
      };

      ws.onmessage = (ev: MessageEvent<string>) => {
        if (!active || typeof ev.data !== "string") return;
        try {
          const parsed = JSON.parse(ev.data) as LogLine;
          console.log("[useLogs] line", parsed);
          setLines((prev) => {
            const next = prev.length >= MAX_LINES
              ? [...prev.slice(prev.length - MAX_LINES + 1), parsed]
              : [...prev, parsed];
            return next;
          });
        } catch (e) {
          console.warn("[useLogs] parse error", e, ev.data);
        }
      };

      ws.onerror = (e) => {
        console.warn("[useLogs] error", e);
      };

      ws.onclose = (e) => {
        console.warn("[useLogs] closed", { code: e.code, reason: e.reason, wasClean: e.wasClean });
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

  return { lines, connected, clear };
}

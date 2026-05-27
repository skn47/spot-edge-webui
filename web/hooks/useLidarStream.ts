"use client";

import { useEffect, useRef, useState } from "react";
import { parseFrame } from "@/lib/parsePointCloud";

export interface LidarStreamState {
  positions: Float32Array | null;
  pointCount: number;
  connected: boolean;
  lastError: string | null;
}

const RECONNECT_BASE_MS = 2_000;
const RECONNECT_MAX_MS = 10_000;

export function useLidarStream(url: string): LidarStreamState {
  const [state, setState] = useState<LidarStreamState>({
    positions: null,
    pointCount: 0,
    connected: false,
    lastError: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const delayRef = useRef(RECONNECT_BASE_MS);

  useEffect(() => {
    let active = true;

    function connect() {
      if (!active) return;
      const ws = new WebSocket(url);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      ws.onopen = () => {
        if (!active) return;
        delayRef.current = RECONNECT_BASE_MS;
        setState((s) => ({ ...s, connected: true, lastError: null }));
      };

      ws.onmessage = (ev: MessageEvent<ArrayBuffer | string>) => {
        if (!active || typeof ev.data === "string") return;
        const frame = parseFrame(ev.data);
        if (!frame) return;
        setState((s) => ({
          ...s,
          positions: frame.positions,
          pointCount: frame.pointCount,
        }));
      };

      ws.onerror = () => {
        if (!active) return;
        setState((s) => ({ ...s, lastError: "WebSocket error" }));
      };

      ws.onclose = () => {
        if (!active) return;
        setState((s) => ({ ...s, connected: false }));
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
  }, [url]);

  return state;
}

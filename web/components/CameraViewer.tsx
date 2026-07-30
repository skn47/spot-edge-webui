"use client";

import { useEffect, useRef, useState } from "react";
import { BACKEND_WS_URL } from "@/lib/constants";

const RECONNECT_BASE_MS = 2_000;
const RECONNECT_MAX_MS = 10_000;

export function CameraViewer() {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const delayRef = useRef(RECONNECT_BASE_MS);
  const prevUrlRef = useRef<string | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let active = true;

    function connect() {
      if (!active) return;
      const ws = new WebSocket(`${BACKEND_WS_URL}/ws/camera/frontleft`);
      ws.binaryType = "blob";
      wsRef.current = ws;

      ws.onopen = () => {
        if (!active) return;
        delayRef.current = RECONNECT_BASE_MS;
        setConnected(true);
      };

      ws.onmessage = (ev: MessageEvent<Blob>) => {
        if (!active || !(ev.data instanceof Blob)) return;
        const url = URL.createObjectURL(ev.data);
        if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current);
        prevUrlRef.current = url;
        if (imgRef.current) imgRef.current.src = url;
      };

      ws.onerror = () => {};

      ws.onclose = () => {
        if (!active) return;
        setConnected(false);
        if (imgRef.current) imgRef.current.src = "";
        if (prevUrlRef.current) {
          URL.revokeObjectURL(prevUrlRef.current);
          prevUrlRef.current = null;
        }
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
      if (prevUrlRef.current) {
        URL.revokeObjectURL(prevUrlRef.current);
        prevUrlRef.current = null;
      }
    };
  }, []);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: "#0a0a0a",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <img
        ref={imgRef}
        alt="Front-left fisheye"
        style={{
          width: "100%",
          height: "100%",
          objectFit: "contain",
          display: "block",
        }}
      />
      {!connected && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 10,
            color: "#3a3a3a",
            fontFamily: "monospace",
            fontSize: 12,
            background: "#0a0a0a",
          }}
        >
          <div
            style={{
              width: 40,
              height: 40,
              border: "2px solid #2a2a2a",
              borderRadius: 6,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 20,
            }}
          >
            ▪
          </div>
          No signal
        </div>
      )}
      <div
        style={{
          position: "absolute",
          top: 16,
          left: 16,
          display: "flex",
          alignItems: "center",
          gap: 5,
          background: "rgba(0,0,0,0.55)",
          padding: "4px 10px",
          borderRadius: 6,
          fontFamily: "monospace",
          fontSize: 11,
          color: connected ? "#00ff88" : "#ff4444",
          pointerEvents: "none",
        }}
      >
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            background: connected ? "#00ff88" : "#ff4444",
            display: "inline-block",
          }}
        />
        FL FISHEYE
      </div>
    </div>
  );
}

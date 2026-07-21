"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BACKEND_WS_URL } from "@/lib/constants";

export interface TeleopVelocity {
  vx: number;
  vy: number;
  omega: number;
}

export interface TeleopHook {
  connected: boolean;
  locked: boolean;
  velocity: TeleopVelocity;
  enabled: boolean;
  setEnabled: (v: boolean) => void;
}

const SEND_HZ = 10;
const SEND_INTERVAL_MS = 1000 / SEND_HZ;
const RECONNECT_BASE_MS = 2_000;
const RECONNECT_MAX_MS = 10_000;
const GAMEPAD_DEADZONE = 0.1;
const LINEAR_SPEED = 0.5;
const ANGULAR_SPEED = 0.6;

const ZERO_VEL: TeleopVelocity = { vx: 0, vy: 0, omega: 0 };

export function useTeleop(): TeleopHook {
  const [enabled, setEnabledState] = useState(false);
  const [connected, setConnected] = useState(false);
  const [locked, setLocked] = useState(false);
  const [velocity, setVelocity] = useState<TeleopVelocity>(ZERO_VEL);

  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const delayRef = useRef(RECONNECT_BASE_MS);
  const enabledRef = useRef(false);
  const lockedRef = useRef(false);

  // Keyboard state
  const keysRef = useRef<Set<string>>(new Set());

  // Send interval
  const sendIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ------------------------------------------------------------------
  // Velocity computation from inputs
  // ------------------------------------------------------------------

  function computeVelocity(): TeleopVelocity {
    // Gamepad takes priority if connected and has input
    const gamepads = navigator.getGamepads?.() ?? [];
    for (const gp of gamepads) {
      if (!gp) continue;
      const ax0 = Math.abs(gp.axes[0] ?? 0) > GAMEPAD_DEADZONE ? gp.axes[0] : 0;
      const ax1 = Math.abs(gp.axes[1] ?? 0) > GAMEPAD_DEADZONE ? gp.axes[1] : 0;
      const ax2 = Math.abs(gp.axes[2] ?? 0) > GAMEPAD_DEADZONE ? gp.axes[2] : 0;
      if (ax0 !== 0 || ax1 !== 0 || ax2 !== 0) {
        return {
          vx: -ax1 * LINEAR_SPEED,   // forward on left stick Y (inverted)
          vy: -ax0 * LINEAR_SPEED,   // lateral on left stick X (inverted)
          omega: -ax2 * ANGULAR_SPEED, // rotation on right stick X (inverted)
        };
      }
    }

    // Keyboard fallback
    const keys = keysRef.current;
    let vx = 0;
    let vy = 0;
    let omega = 0;
    if (keys.has("w") || keys.has("ArrowUp")) vx += LINEAR_SPEED;
    if (keys.has("s") || keys.has("ArrowDown")) vx -= LINEAR_SPEED;
    if (keys.has("a")) vy += LINEAR_SPEED;
    if (keys.has("d")) vy -= LINEAR_SPEED;
    if (keys.has("ArrowLeft")) omega += ANGULAR_SPEED;
    if (keys.has("ArrowRight")) omega -= ANGULAR_SPEED;
    return { vx, vy, omega };
  }

  // ------------------------------------------------------------------
  // WebSocket lifecycle
  // ------------------------------------------------------------------

  const connectWs = useCallback(() => {
    if (!enabledRef.current) return;

    const ws = new WebSocket(`${BACKEND_WS_URL}/ws/teleop`);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!enabledRef.current) { ws.close(); return; }
      delayRef.current = RECONNECT_BASE_MS;
      setConnected(true);
    };

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string);
        if (msg.type === "error" && msg.message === "teleop_locked") {
          lockedRef.current = true;
          setLocked(true);
        }
      } catch {}
    };

    ws.onerror = () => {};

    ws.onclose = () => {
      setConnected(false);
      if (!enabledRef.current || lockedRef.current) return;
      timerRef.current = setTimeout(() => {
        delayRef.current = Math.min(delayRef.current * 2, RECONNECT_MAX_MS);
        connectWs();
      }, delayRef.current);
    };
  }, []);

  // ------------------------------------------------------------------
  // Enable/disable
  // ------------------------------------------------------------------

  const setEnabled = useCallback((v: boolean) => {
    enabledRef.current = v;
    setEnabledState(v);

    if (!v) {
      if (timerRef.current !== null) clearTimeout(timerRef.current);
      if (sendIntervalRef.current !== null) clearInterval(sendIntervalRef.current);
      wsRef.current?.close();
      wsRef.current = null;
      setConnected(false);
      setVelocity(ZERO_VEL);
      lockedRef.current = false;
      setLocked(false);
    } else {
      connectWs();
      sendIntervalRef.current = setInterval(() => {
        if (!enabledRef.current || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
        const vel = computeVelocity();
        setVelocity(vel);
        wsRef.current.send(JSON.stringify(vel));
      }, SEND_INTERVAL_MS);
    }
  }, [connectWs]);

  // ------------------------------------------------------------------
  // Keyboard listeners
  // ------------------------------------------------------------------

  useEffect(() => {
    const onDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (["w", "a", "s", "d", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)) {
        e.preventDefault();
        keysRef.current.add(e.key);
      }
    };
    const onUp = (e: KeyboardEvent) => {
      keysRef.current.delete(e.key);
    };
    window.addEventListener("keydown", onDown);
    window.addEventListener("keyup", onUp);
    return () => {
      window.removeEventListener("keydown", onDown);
      window.removeEventListener("keyup", onUp);
    };
  }, []);

  // ------------------------------------------------------------------
  // Cleanup on unmount
  // ------------------------------------------------------------------

  useEffect(() => {
    return () => {
      enabledRef.current = false;
      if (timerRef.current !== null) clearTimeout(timerRef.current);
      if (sendIntervalRef.current !== null) clearInterval(sendIntervalRef.current);
      wsRef.current?.close();
    };
  }, []);

  return { connected, locked, velocity, enabled, setEnabled };
}

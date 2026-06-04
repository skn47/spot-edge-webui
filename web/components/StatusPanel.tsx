"use client";

import type { CSSProperties } from "react";
import { useEffect } from "react";
import { useRobotState } from "@/hooks/useRobotState";

const S = {
  panel: {
    background: "#0d0d0d",
    borderBottom: "1px solid #222",
    padding: "12px 14px",
    fontFamily: "monospace",
    fontSize: "12px",
    color: "#ccc",
  } as CSSProperties,
  sectionTitle: {
    color: "#555",
    fontSize: "10px",
    textTransform: "uppercase" as const,
    letterSpacing: "0.08em",
    marginBottom: "6px",
  },
  row: {
    display: "flex",
    justifyContent: "space-between",
    marginBottom: "3px",
  } as CSSProperties,
  label: { color: "#666" },
  value: { color: "#e0e0e0" },
  dot: (on: boolean) => ({
    display: "inline-block",
    width: 7,
    height: 7,
    borderRadius: "50%",
    background: on ? "#00ff88" : "#333",
    marginRight: 6,
  } as CSSProperties),
  processRow: {
    display: "flex",
    alignItems: "center",
    marginBottom: "4px",
  } as CSSProperties,
  badge: (color: string) => ({
    fontSize: "10px",
    padding: "1px 6px",
    borderRadius: 3,
    background: color,
    color: "#000",
    fontWeight: 700,
  } as CSSProperties),
  connBadge: (ok: boolean) => ({
    display: "inline-flex",
    alignItems: "center",
    gap: 5,
    fontSize: "10px",
    color: ok ? "#00ff88" : "#ff4444",
  } as CSSProperties),
};

function fmt(n: number) {
  return n.toFixed(2);
}

export function StatusPanel() {
  const { state, connected } = useRobotState();

  useEffect(() => {
    console.log("[StatusPanel] mounted");
    return () => console.log("[StatusPanel] unmounted");
  }, []);

  const missionColor = state?.mission_paused
    ? "#f5a623"
    : state?.mission_active
    ? "#00ff88"
    : "#444";

  const missionLabel = state?.mission_paused
    ? "Paused"
    : state?.mission_active
    ? "Active"
    : "Idle";

  return (
    <div style={S.panel}>
      {/* Connection */}
      <div style={{ marginBottom: 10 }}>
        <span style={S.connBadge(connected)}>
          <span style={S.dot(connected)} />
          {connected ? "Connected" : "Disconnected"}
        </span>
      </div>

      {/* Odometry */}
      <div style={{ marginBottom: 10 }}>
        <div style={S.sectionTitle}>Odometry</div>
        {state?.odometry ? (
          <>
            <div style={S.row}>
              <span style={S.label}>X</span>
              <span style={S.value}>{fmt(state.odometry.x)} m</span>
            </div>
            <div style={S.row}>
              <span style={S.label}>Y</span>
              <span style={S.value}>{fmt(state.odometry.y)} m</span>
            </div>
            <div style={S.row}>
              <span style={S.label}>Yaw</span>
              <span style={S.value}>{fmt((state.odometry.yaw * 180) / Math.PI)}°</span>
            </div>
          </>
        ) : (
          <div style={{ color: "#444" }}>—</div>
        )}
      </div>

      {/* Mission */}
      <div style={{ marginBottom: 10 }}>
        <div style={S.sectionTitle}>Mission</div>
        <span style={S.badge(missionColor)}>{missionLabel}</span>
      </div>

      {/* Processes */}
      <div>
        <div style={S.sectionTitle}>Processes</div>
        {state
          ? Object.entries(state.process_statuses).map(([name, status]) => (
              <div key={name} style={S.processRow}>
                <span style={S.dot(status.running)} />
                <span style={S.label}>{name}</span>
                {status.running && status.pid != null && (
                  <span style={{ ...S.label, marginLeft: "auto", color: "#444", fontSize: 10 }}>
                    pid {status.pid}
                  </span>
                )}
              </div>
            ))
          : <div style={{ color: "#444" }}>—</div>
        }
      </div>
    </div>
  );
}

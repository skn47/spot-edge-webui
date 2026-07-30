"use client";

import { useState } from "react";
import { LidarViewer } from "./LidarViewer";
import { CameraViewer } from "./CameraViewer";
import { VoltageBadge } from "./VoltageBadge";

type View = "lidar" | "camera";

export function ViewportPanel() {
  const [view, setView] = useState<View>("lidar");

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      {view === "lidar" ? <LidarViewer /> : <CameraViewer />}
      <VoltageBadge />
      <button
        onClick={() => setView(v => (v === "lidar" ? "camera" : "lidar"))}
        style={{
          position: "absolute",
          top: 16,
          right: 16,
          zIndex: 10,
          background: "rgba(0,0,0,0.55)",
          border: "1px solid #333",
          borderRadius: 6,
          color: "#ccc",
          fontFamily: "monospace",
          fontSize: 12,
          padding: "5px 12px",
          cursor: "pointer",
        }}
      >
        {view === "lidar" ? "Camera" : "LiDAR"}
      </button>
    </div>
  );
}

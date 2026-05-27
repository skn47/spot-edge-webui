"use client";

import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useLidarStream } from "@/hooks/useLidarStream";
import { PointCloud } from "@/components/PointCloud";
import { WS_URL } from "@/lib/constants";

function ConnectionBadge({ connected }: { connected: boolean }) {
  return (
    <div
      style={{
        position: "absolute",
        top: 16,
        left: 16,
        zIndex: 10,
        display: "flex",
        alignItems: "center",
        gap: 8,
        background: "rgba(0,0,0,0.55)",
        padding: "6px 12px",
        borderRadius: 6,
        color: "#fff",
        fontFamily: "monospace",
        fontSize: 13,
      }}
    >
      <span
        style={{
          width: 10,
          height: 10,
          borderRadius: "50%",
          background: connected ? "#00ff88" : "#ff4444",
          display: "inline-block",
        }}
      />
      {connected ? "Live" : "Reconnecting…"}
    </div>
  );
}

export function LidarViewer() {
  const { positions, pointCount, connected } = useLidarStream(WS_URL);

  return (
    <div style={{ width: "100vw", height: "100vh", background: "#0a0a0a" }}>
      <ConnectionBadge connected={connected} />
      <Canvas camera={{ position: [0, 5, 10], fov: 60 }}>
        <ambientLight intensity={0.5} />
        <OrbitControls makeDefault />
        {positions && positions.length > 0 && (
          <PointCloud positions={positions} pointCount={pointCount} />
        )}
      </Canvas>
    </div>
  );
}

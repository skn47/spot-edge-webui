import { LidarViewer } from "@/components/LidarViewer";
import { StatusPanel } from "@/components/StatusPanel";
import { ControlPanel } from "@/components/ControlPanel";
import { LogPanel } from "@/components/LogPanel";

export default function Home() {
  return (
    <div style={{ display: "flex", width: "100vw", height: "100vh", overflow: "hidden" }}>
      <div style={{ flex: 1, position: "relative", minWidth: 0, overflow: "hidden" }}>
        <LidarViewer />
      </div>
      <div
        style={{
          width: 320,
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          background: "#0a0a0a",
          borderLeft: "1px solid #1e1e1e",
          minHeight: 0,
          position: "relative",
          zIndex: 1,
        }}
      >
        <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
          <StatusPanel />
          <ControlPanel />
        </div>
        <LogPanel />
      </div>
    </div>
  );
}

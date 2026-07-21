"use client";

import type { CSSProperties } from "react";
import { useEffect, useRef, useState } from "react";
import {
  clearRoute,
  fetchMaps,
  missionAction,
  missionStart,
  processAction,
  ProcessResponse,
  setDriverCredentials,
  uploadRoute,
} from "@/lib/api";
import { PROCESS_LABELS } from "@/lib/constants";
import { useRobotState } from "@/hooks/useRobotState";
import { useTeleop } from "@/hooks/useTeleop";

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const S = {
  panel: {
    background: "#0a0a0a",
    padding: "12px 14px",
    fontFamily: "monospace",
    fontSize: "12px",
    color: "#ccc",
    flex: 1,
    overflowY: "auto" as const,
  } as CSSProperties,
  sectionTitle: {
    color: "#555",
    fontSize: "10px",
    textTransform: "uppercase" as const,
    letterSpacing: "0.08em",
    marginBottom: "6px",
    marginTop: "12px",
  },
  row: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: "6px",
  } as CSSProperties,
  label: { color: "#888", flexShrink: 0 },
  btn: (color: string, disabled?: boolean) => ({
    padding: "3px 10px",
    borderRadius: 4,
    border: "none",
    cursor: disabled ? "not-allowed" : "pointer",
    background: disabled ? "#222" : color,
    color: disabled ? "#444" : "#000",
    fontFamily: "monospace",
    fontSize: "11px",
    fontWeight: 700,
    opacity: disabled ? 0.5 : 1,
    minWidth: 46,
  } as CSSProperties),
  btnGreen: (disabled?: boolean) =>
    S.btn("#00ff88", disabled),
  btnRed: (disabled?: boolean) =>
    S.btn("#ff4444", disabled),
  btnYellow: (disabled?: boolean) =>
    S.btn("#f5a623", disabled),
  btnGray: (disabled?: boolean) =>
    S.btn("#555", disabled),
  estopBtn: {
    width: "100%",
    padding: "10px",
    background: "#cc0000",
    color: "#fff",
    border: "2px solid #ff0000",
    borderRadius: 6,
    fontFamily: "monospace",
    fontSize: "14px",
    fontWeight: 900,
    cursor: "pointer",
    letterSpacing: "0.1em",
    marginTop: 12,
  } as CSSProperties,
  select: {
    background: "#1a1a1a",
    color: "#ccc",
    border: "1px solid #333",
    borderRadius: 4,
    padding: "3px 6px",
    fontFamily: "monospace",
    fontSize: "11px",
    flex: 1,
    marginLeft: 8,
  } as CSSProperties,
  input: {
    background: "#1a1a1a",
    border: "1px solid #333",
    borderRadius: 4,
    color: "#eee",
    fontSize: 11,
    fontFamily: "monospace",
    padding: "3px 6px",
    width: 130,
  } as CSSProperties,
  flash: (msg: string | null) => ({
    fontSize: "10px",
    color: msg && msg.startsWith("Error") ? "#ff4444" : "#00ff88",
    minHeight: 14,
    marginBottom: 4,
  } as CSSProperties),
};

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function useFlash(): [string | null, (msg: string) => void] {
  const [msg, setMsg] = useState<string | null>(null);
  const flash = (m: string) => {
    setMsg(m);
    setTimeout(() => setMsg(null), 3000);
  };
  return [msg, flash];
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ControlPanel() {
  const { state } = useRobotState();
  const { connected: teleopConnected, locked: teleopLocked, velocity, enabled: teleopEnabled, setEnabled: setTeleopEnabled } = useTeleop();

  const [driverHostname, setDriverHostname] = useState("192.168.80.3");
  const [driverUsername, setDriverUsername] = useState("");
  const [driverPassword, setDriverPassword] = useState("");
  const [credentialsSaved, setCredentialsSaved] = useState(false);

  const [maps, setMaps] = useState<string[]>([]);
  const [selectedMap, setSelectedMap] = useState("microgrid");
  const [uploadedRoute, setUploadedRoute] = useState<string | null>(null);
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [flash, setFlash] = useFlash();
  const routeInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    console.log("[ControlPanel] mounted");
    fetchMaps()
      .then((m) => {
        console.log("[ControlPanel] /api/maps ->", m);
        if (m.length > 0) {
          setMaps(m);
          setSelectedMap(m[0]);
        }
      })
      .catch((e) => console.warn("[ControlPanel] /api/maps error", e));
    return () => console.log("[ControlPanel] unmounted");
  }, []);

  // Disable teleop automatically when mission becomes active
  useEffect(() => {
    if (state?.mission_active && teleopEnabled) {
      setTeleopEnabled(false);
    }
  }, [state?.mission_active, teleopEnabled, setTeleopEnabled]);

  const busy = (key: string) => loading[key] === true;
  const setBusy = (key: string, v: boolean) =>
    setLoading((l) => ({ ...l, [key]: v }));

  const MAP_SENSITIVE = new Set(["localization", "navigation"]);

  async function handleSaveCredentials() {
    setBusy("driver-creds", true);
    try {
      await setDriverCredentials(driverHostname, driverUsername, driverPassword);
      setCredentialsSaved(true);
      setFlash("Robot credentials saved");
    } catch (e: unknown) {
      setFlash(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy("driver-creds", false);
    }
  }

  async function handleProcess(action: "start" | "stop" | "restart", name: string) {
    const key = `${action}-${name}`;
    setBusy(key, true);
    try {
      const mapName = action !== "stop" && MAP_SENSITIVE.has(name) ? selectedMap : undefined;
      const r: ProcessResponse = await processAction(action, name, mapName);
      setFlash(r.message);
    } catch (e: unknown) {
      setFlash(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(key, false);
    }
  }

  async function handleRouteClear() {
    setBusy("route-clear", true);
    try {
      await clearRoute();
      setUploadedRoute(null);
      setFlash("Route cleared (fallback: midpoint)");
    } catch (err: unknown) {
      setFlash(`Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy("route-clear", false);
    }
  }

  async function handleRouteUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy("route-upload", true);
    try {
      const r = await uploadRoute(file);
      setUploadedRoute(r.filename);
      setFlash(`Route loaded: ${r.filename} (${r.goal_count} goals)`);
    } catch (err: unknown) {
      setFlash(`Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy("route-upload", false);
      if (routeInputRef.current) routeInputRef.current.value = "";
    }
  }

  async function handleMissionStart() {
    setBusy("mission-start", true);
    try {
      const r = await missionStart(selectedMap);
      setFlash(r.message);
    } catch (e: unknown) {
      setFlash(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy("mission-start", false);
    }
  }

  async function handleMission(action: "stop" | "pause" | "resume" | "home") {
    setBusy(`mission-${action}`, true);
    try {
      const r = await missionAction(action);
      setFlash(r.message);
    } catch (e: unknown) {
      setFlash(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(`mission-${action}`, false);
    }
  }

  async function handleEstop() {
    if (!window.confirm("Confirm E-Stop? This will immediately stop all motion and kill the mission stack.")) return;
    setBusy("estop", true);
    try {
      const r = await missionAction("estop");
      setFlash(r.message);
    } catch (e: unknown) {
      setFlash(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy("estop", false);
    }
  }

  const missionActive = state?.mission_active ?? false;
  const missionPaused = state?.mission_paused ?? false;

  const processStatuses = state?.process_statuses ?? {};

  return (
    <div style={S.panel}>
      <div style={S.flash(flash)}>{flash}</div>

      {/* ---- Robot connection ---- */}
      <div style={S.sectionTitle}>Robot Connection</div>
      <div style={S.row}>
        <span style={S.label}>Host</span>
        <input
          style={S.input}
          value={driverHostname}
          onChange={e => { setDriverHostname(e.target.value); setCredentialsSaved(false); }}
          placeholder="192.168.80.3"
        />
      </div>
      <div style={S.row}>
        <span style={S.label}>Username</span>
        <input
          style={S.input}
          value={driverUsername}
          onChange={e => { setDriverUsername(e.target.value); setCredentialsSaved(false); }}
          placeholder="username"
        />
      </div>
      <div style={S.row}>
        <span style={S.label}>Password</span>
        <input
          style={S.input}
          type="password"
          value={driverPassword}
          onChange={e => { setDriverPassword(e.target.value); setCredentialsSaved(false); }}
          placeholder="password"
        />
      </div>
      <div style={S.row}>
        <span style={{ ...S.label, color: credentialsSaved ? "#00ff88" : "#555", fontSize: 10 }}>
          {credentialsSaved ? "saved" : "not saved"}
        </span>
        <button
          style={S.btnGray(busy("driver-creds") || !driverUsername || !driverPassword)}
          disabled={busy("driver-creds") || !driverUsername || !driverPassword}
          onClick={handleSaveCredentials}
        >
          {busy("driver-creds") ? "…" : "Save"}
        </button>
      </div>

      {/* ---- Process controls ---- */}
      <div style={S.sectionTitle}>Process Controls</div>
      {Object.keys(PROCESS_LABELS).map((name) => {
        const running = processStatuses[name]?.running ?? false;
        return (
          <div key={name} style={S.row}>
            <span style={S.label}>{PROCESS_LABELS[name]}</span>
            <div style={{ display: "flex", gap: 4 }}>
              <button
                style={S.btnGreen(running || busy(`start-${name}`))}
                disabled={running || busy(`start-${name}`)}
                onClick={() => handleProcess("start", name)}
              >
                {busy(`start-${name}`) ? "…" : "Start"}
              </button>
              <button
                style={S.btnRed(!running || busy(`stop-${name}`))}
                disabled={!running || busy(`stop-${name}`)}
                onClick={() => handleProcess("stop", name)}
              >
                {busy(`stop-${name}`) ? "…" : "Stop"}
              </button>
            </div>
          </div>
        );
      })}

      {/* ---- Route ---- */}
      <div style={S.sectionTitle}>Route</div>
      <div style={S.row}>
        <span style={{ ...S.label, fontSize: 10, color: uploadedRoute ? "#00ff88" : "#555", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const, maxWidth: 130 }}>
          {uploadedRoute ?? "no route loaded"}
        </span>
        <div style={{ display: "flex", gap: 4 }}>
          {uploadedRoute && (
            <button
              style={S.btnRed(busy("route-clear"))}
              disabled={busy("route-clear")}
              onClick={handleRouteClear}
            >
              {busy("route-clear") ? "…" : "✕"}
            </button>
          )}
          <button
            style={S.btnGray(busy("route-upload"))}
            disabled={busy("route-upload")}
            onClick={() => routeInputRef.current?.click()}
          >
            {busy("route-upload") ? "…" : "Upload"}
          </button>
          <input
            ref={routeInputRef}
            type="file"
            accept=".json"
            style={{ display: "none" }}
            onChange={handleRouteUpload}
          />
        </div>
      </div>

      {/* ---- Mission controls ---- */}
      <div style={S.sectionTitle}>Mission Controls</div>

      {/* Map selector */}
      {!missionActive && (
        <div style={{ ...S.row, marginBottom: 8 }}>
          <span style={S.label}>Map</span>
          <select
            style={S.select}
            value={selectedMap}
            onChange={(e) => setSelectedMap(e.target.value)}
          >
            {maps.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
      )}

      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" as const, marginBottom: 6 }}>
        <button
          style={S.btnGreen(missionActive || busy("mission-start"))}
          disabled={missionActive || busy("mission-start")}
          onClick={handleMissionStart}
        >
          {busy("mission-start") ? "Starting…" : "Start"}
        </button>
        <button
          style={S.btnRed(!missionActive || busy("mission-stop"))}
          disabled={!missionActive || busy("mission-stop")}
          onClick={() => handleMission("stop")}
        >
          {busy("mission-stop") ? "…" : "Stop"}
        </button>
        <button
          style={S.btnYellow(!missionActive || busy(`mission-${missionPaused ? "resume" : "pause"}`))}
          disabled={!missionActive || busy(`mission-${missionPaused ? "resume" : "pause"}`)}
          onClick={() => handleMission(missionPaused ? "resume" : "pause")}
        >
          {missionPaused ? "Resume" : "Pause"}
        </button>
        <button
          style={S.btnGray(!missionActive || busy("mission-home"))}
          disabled={!missionActive || busy("mission-home")}
          onClick={() => handleMission("home")}
        >
          Home
        </button>
      </div>

      {/* ---- Teleop ---- */}
      <div style={S.sectionTitle}>Teleoperation</div>
      <div style={S.row}>
        <span style={S.label}>WASD / Gamepad</span>
        <button
          style={teleopEnabled ? S.btnRed(missionActive) : S.btnGreen(missionActive)}
          disabled={missionActive}
          onClick={() => setTeleopEnabled(!teleopEnabled)}
        >
          {teleopEnabled ? "Disable" : "Enable"}
        </button>
      </div>
      {teleopEnabled && (
        <div style={{ color: "#555", fontSize: 10, marginBottom: 4 }}>
          {teleopConnected ? (
            <span style={{ color: "#00ff88" }}>
              ● vx {velocity.vx.toFixed(2)} vy {velocity.vy.toFixed(2)} ω {velocity.omega.toFixed(2)}
            </span>
          ) : (
            <span style={{ color: teleopLocked ? "#f5a623" : "#ff4444" }}>
          {teleopLocked ? "● locked (another client active)" : "● disconnected"}
        </span>
          )}
        </div>
      )}

      {/* ---- E-Stop ---- */}
      <button
        style={S.estopBtn}
        disabled={busy("estop")}
        onClick={handleEstop}
      >
        {busy("estop") ? "STOPPING…" : "⬛ E-STOP"}
      </button>
    </div>
  );
}

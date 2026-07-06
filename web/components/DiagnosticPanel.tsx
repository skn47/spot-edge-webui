"use client";

import type { CSSProperties } from "react";
import { useState, useCallback } from "react";
import { runDiagnostic, type DiagnosticResult, type TopicInfo } from "@/lib/api";

const S = {
  panel: {
    background: "#0d0d0d",
    borderBottom: "1px solid #222",
    fontFamily: "monospace",
    fontSize: "12px",
    color: "#ccc",
  } as CSSProperties,
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "8px 14px",
    cursor: "pointer",
    userSelect: "none",
    borderBottom: "1px solid #1a1a1a",
  } as CSSProperties,
  headerTitle: {
    color: "#555",
    fontSize: "10px",
    textTransform: "uppercase" as const,
    letterSpacing: "0.08em",
  },
  body: {
    padding: "10px 14px",
  } as CSSProperties,
  btn: (disabled: boolean) => ({
    background: disabled ? "#1a1a1a" : "#1e1e1e",
    border: "1px solid #333",
    color: disabled ? "#444" : "#aaa",
    fontSize: "11px",
    fontFamily: "monospace",
    padding: "4px 10px",
    borderRadius: 3,
    cursor: disabled ? "default" : "pointer",
  } as CSSProperties),
  row: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: "4px",
    gap: 8,
  } as CSSProperties,
  label: { color: "#666", flexShrink: 0 } as CSSProperties,
  sectionTitle: {
    color: "#555",
    fontSize: "10px",
    textTransform: "uppercase" as const,
    letterSpacing: "0.08em",
    marginTop: "10px",
    marginBottom: "5px",
  } as CSSProperties,
  dot: (ok: boolean | null) => ({
    display: "inline-block",
    width: 7,
    height: 7,
    borderRadius: "50%",
    background: ok === null ? "#333" : ok ? "#00ff88" : "#ff4444",
    marginRight: 6,
    flexShrink: 0,
    marginTop: 2,
  } as CSSProperties),
  warn: {
    color: "#f5a623",
    fontSize: "10px",
    marginLeft: 13,
    marginBottom: 2,
  } as CSSProperties,
  dim: { color: "#444", fontSize: "10px" } as CSSProperties,
  counts: { color: "#888", fontSize: "10px", textAlign: "right" as const },
};

function TopicRow({ topic, info }: { topic: string; info: TopicInfo }) {
  return (
    <div style={{ marginBottom: 4 }}>
      <div style={S.row}>
        <span style={{ display: "flex", alignItems: "flex-start" }}>
          <span style={S.dot(info.exists ? info.ok : false)} />
          <span style={S.label}>{info.label}</span>
        </span>
        {info.exists ? (
          <span style={S.counts}>
            {info.publishers}↑ {info.subscribers}↓
          </span>
        ) : (
          <span style={S.dim}>not found</span>
        )}
      </div>
      {info.warning && <div style={S.warn}>⚠ {info.warning}</div>}
    </div>
  );
}

export function DiagnosticPanel() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DiagnosticResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runCheck = useCallback(async (e: React.MouseEvent) => {
    e.stopPropagation();
    setLoading(true);
    setError(null);
    try {
      const r = await runDiagnostic();
      setResult(r);
      if (!open) setOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Diagnostic failed");
    } finally {
      setLoading(false);
    }
  }, [open]);

  const checks = result?.checks;
  const nodeCount = checks?.nodes.found.length ?? 0;
  const missingNodes = checks?.nodes.missing ?? [];

  return (
    <div style={S.panel}>
      <div style={S.header} onClick={() => setOpen(o => !o)}>
        <span style={S.headerTitle}>
          <span
            style={{
              ...S.dot(result ? result.ok : null),
              display: "inline-block",
              verticalAlign: "middle",
              marginBottom: 1,
            }}
          />
          System Check
          {result && (
            <span style={{ color: result.ok ? "#00ff88" : "#ff4444", marginLeft: 6 }}>
              {result.ok ? "PASS" : "FAIL"}
            </span>
          )}
        </span>
        <button style={S.btn(loading)} onClick={runCheck} disabled={loading}>
          {loading ? "Running…" : "Run Check"}
        </button>
      </div>

      {open && (
        <div style={S.body}>
          {error && <div style={{ color: "#ff4444", marginBottom: 8 }}>{error}</div>}

          {!result && !loading && (
            <div style={S.dim}>Press "Run Check" to probe the ROS 2 / Zenoh stack.</div>
          )}

          {result && (
            <>
              {/* Zenoh router */}
              <div style={S.sectionTitle}>Zenoh Router</div>
              <div style={{ display: "flex", alignItems: "flex-start", marginBottom: 4 }}>
                <span style={S.dot(checks!.zenoh_router.ok)} />
                <span style={{ color: checks!.zenoh_router.ok ? "#e0e0e0" : "#ff4444" }}>
                  {checks!.zenoh_router.detail}
                </span>
              </div>

              {/* Nodes */}
              <div style={S.sectionTitle}>Nodes ({nodeCount} visible)</div>
              {missingNodes.length > 0 && (
                <div style={S.warn}>
                  ⚠ Not visible: {missingNodes.join(", ")}
                  {" — "}may not be started, or on wrong RMW
                </div>
              )}
              {missingNodes.length === 0 && nodeCount > 0 && (
                <div style={{ color: "#00ff88", marginBottom: 4 }}>All expected nodes visible</div>
              )}
              {nodeCount === 0 && (
                <div style={{ color: "#ff4444", marginBottom: 4 }}>
                  No nodes visible — Zenoh router likely not running
                </div>
              )}

              {/* Topics */}
              <div style={S.sectionTitle}>Topics (↑pub ↓sub)</div>
              {Object.entries(checks!.topics).map(([topic, info]) => (
                <TopicRow key={topic} topic={topic} info={info} />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

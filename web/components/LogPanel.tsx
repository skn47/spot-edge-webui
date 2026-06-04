"use client";

import type { CSSProperties } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLogs } from "@/hooks/useLogs";

function useMountLog(name: string) {
  useEffect(() => {
    console.log(`[${name}] mounted`);
    return () => console.log(`[${name}] unmounted`);
  }, [name]);
}

const SOURCES = [
  "all",
  "lidar_stream",
  "sensors",
  "localization",
  "navigation",
  "route_manager",
] as const;

const S = {
  panel: {
    background: "#0d0d0d",
    borderTop: "1px solid #222",
    fontFamily: "monospace",
    fontSize: "11px",
    color: "#ccc",
    display: "flex",
    flexDirection: "column" as const,
  } as CSSProperties,
  header: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "8px 12px",
    cursor: "pointer",
    background: "#111",
    userSelect: "none" as const,
  } as CSSProperties,
  headerTitle: {
    fontSize: "10px",
    textTransform: "uppercase" as const,
    letterSpacing: "0.08em",
    color: "#888",
    flex: 1,
  },
  dot: (on: boolean): CSSProperties => ({
    display: "inline-block",
    width: 7,
    height: 7,
    borderRadius: "50%",
    background: on ? "#00ff88" : "#444",
  }),
  count: { color: "#555", fontSize: "10px" } as CSSProperties,
  toolbar: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "6px 10px",
    borderBottom: "1px solid #1c1c1c",
  } as CSSProperties,
  select: {
    background: "#1a1a1a",
    color: "#ccc",
    border: "1px solid #333",
    borderRadius: 3,
    padding: "2px 5px",
    fontFamily: "monospace",
    fontSize: "10px",
    flex: 1,
  } as CSSProperties,
  btn: {
    padding: "2px 8px",
    background: "#333",
    color: "#ccc",
    border: "none",
    borderRadius: 3,
    fontFamily: "monospace",
    fontSize: "10px",
    cursor: "pointer",
  } as CSSProperties,
  body: (height: number): CSSProperties => ({
    height,
    overflowY: "auto",
    padding: "6px 10px",
    background: "#080808",
    lineHeight: 1.35,
  }),
  line: (isErr: boolean): CSSProperties => ({
    color: isErr ? "#ff6b6b" : "#bbb",
    whiteSpace: "pre-wrap",
    wordBreak: "break-all",
  }),
  source: (isErr: boolean): CSSProperties => ({
    color: isErr ? "#ff4444" : "#666",
    marginRight: 6,
  }),
  empty: { color: "#444", padding: "8px 0" } as CSSProperties,
};

export function LogPanel() {
  useMountLog("LogPanel");
  const { lines, connected, clear } = useLogs();
  const [expanded, setExpanded] = useState(false);
  const [sourceFilter, setSourceFilter] = useState<(typeof SOURCES)[number]>("all");

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const stickRef = useRef(true); // are we pinned to the bottom?

  const visibleLines = useMemo(() => {
    if (sourceFilter === "all") return lines;
    return lines.filter((l) => l.source === sourceFilter);
  }, [lines, sourceFilter]);

  // Auto-scroll only when user is pinned to the bottom.
  useEffect(() => {
    if (!expanded || !scrollRef.current || !stickRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [visibleLines, expanded]);

  function onScroll() {
    const el = scrollRef.current;
    if (!el) return;
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight;
    stickRef.current = dist < 24;
  }

  return (
    <div style={S.panel}>
      <div style={S.header} onClick={() => setExpanded((v) => !v)}>
        <span style={S.dot(connected)} />
        <span style={S.headerTitle}>Logs</span>
        <span style={S.count}>{lines.length}</span>
        <span style={{ color: "#666", fontSize: 10 }}>{expanded ? "▼" : "▶"}</span>
      </div>

      {expanded && (
        <>
          <div style={S.toolbar}>
            <select
              style={S.select}
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value as (typeof SOURCES)[number])}
            >
              {SOURCES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <button
              style={S.btn}
              onClick={(e) => {
                e.stopPropagation();
                clear();
                stickRef.current = true;
              }}
            >
              clear
            </button>
          </div>

          <div ref={scrollRef} onScroll={onScroll} style={S.body(240)}>
            {visibleLines.length === 0 ? (
              <div style={S.empty}>— no log lines —</div>
            ) : (
              visibleLines.map((l, i) => {
                const isErr = l.stream === "stderr";
                return (
                  <div key={i} style={S.line(isErr)}>
                    <span style={S.source(isErr)}>[{l.source}]</span>
                    {l.text}
                  </div>
                );
              })
            )}
          </div>
        </>
      )}
    </div>
  );
}

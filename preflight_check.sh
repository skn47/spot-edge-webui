#!/usr/bin/env bash
# preflight_check.sh — ROS 2 / Zenoh communication health check
#
# Run this before any field mission to verify all nodes are communicating.
# Usage: ./preflight_check.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREEN="\033[0;32m"; RED="\033[0;31m"; YELLOW="\033[0;33m"; RESET="\033[0m"
FAILED=0

ok()   { echo -e "  ${GREEN}✓${RESET} $1"; }
fail() { echo -e "  ${RED}✗${RESET} $1"; FAILED=1; }
warn() { echo -e "  ${YELLOW}⚠${RESET} $1"; }

echo "════════════════════════════════════════"
echo "  Spot Edge Nav — Pre-flight Check"
echo "════════════════════════════════════════"

# ── 1. Source environment ──────────────────────────────────────────────────
echo ""
echo "── Environment"
# shellcheck source=/dev/null
source /opt/ros/humble/setup.bash 2>/dev/null \
  || { fail "Cannot source /opt/ros/humble/setup.bash"; exit 1; }
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/install/setup.bash" 2>/dev/null \
  || { fail "Cannot source workspace install/setup.bash — run 'colcon build' first"; exit 1; }
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
ok "ROS 2 Humble + workspace sourced  (RMW: rmw_zenoh_cpp)"

# ── 2. Zenoh router ────────────────────────────────────────────────────────
echo ""
echo "── Zenoh Router"
if python3 -c "import socket; socket.create_connection(('localhost',7447),2).close()" 2>/dev/null; then
  ok "Router reachable at localhost:7447"
else
  fail "Router NOT reachable at localhost:7447 — run ./zenoh_host.sh first"
fi

# ── 3. Node discovery ──────────────────────────────────────────────────────
echo ""
echo "── Node Discovery"
NODES=$(ros2 node list 2>/dev/null || true)
if [ -z "$NODES" ]; then
  fail "No nodes visible — Zenoh routing may be broken or no nodes started"
else
  NODE_COUNT=$(echo "$NODES" | grep -c . || true)
  ok "${NODE_COUNT} node(s) visible"
  for N in spot_driver_node fastlio_mapping localization_node far_planner \
            regulated_pure_pursuit_controller route_manager terrain_processor; do
    if echo "$NODES" | grep -q "${N}"; then
      ok "  ${N}"
    else
      warn "  ${N} — not visible (not started, or wrong RMW)"
    fi
  done
fi

# ── 4. Topic health ────────────────────────────────────────────────────────
echo ""
echo "── Topic Health  (↑pub ↓sub)"

check_topic() {
  local TOPIC="$1" LABEL="$2" MIN_PUB="$3" MIN_SUB="$4"
  local INFO PUBS SUBS
  INFO=$(ros2 topic info "${TOPIC}" 2>/dev/null || true)
  if [ -z "$INFO" ]; then
    warn "${TOPIC}  (${LABEL}) — not found"
    return
  fi
  PUBS=$(echo "$INFO" | grep -oP 'Publisher count: \K\d+' || echo 0)
  SUBS=$(echo "$INFO" | grep -oP 'Subscription count: \K\d+' || echo 0)
  printf "  %-30s  %s↑  %s↓\n" "${TOPIC}" "${PUBS}" "${SUBS}"
  [ "${PUBS}" -lt "${MIN_PUB}" ] && \
    warn "    expected ≥${MIN_PUB} publisher(s) — ${LABEL} may not be publishing"
  [ "${SUBS}" -lt "${MIN_SUB}" ] && \
    warn "    expected ≥${MIN_SUB} subscriber(s) — check RMW isolation (wrong rmw_zenoh_cpp?)"
}

check_topic "/velodyne_points"  "LiDAR driver"       1 0
check_topic "/odometry_map"     "Localization"        1 1
check_topic "/cmd_vel"          "Path follower→robot" 0 1
check_topic "/goal_pose"        "Route manager"       0 1
check_topic "/far_path"         "FAR Planner"         1 1

# ── Summary ────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
if [ "${FAILED}" -eq 0 ]; then
  echo -e "  ${GREEN}All critical checks passed. Safe to start mission.${RESET}"
else
  echo -e "  ${RED}One or more critical checks FAILED.${RESET}"
  echo "  Review the output above before starting a mission."
  echo "  Common fix: ensure zenoh_host.sh is running and all"
  echo "  nodes were started with RMW_IMPLEMENTATION=rmw_zenoh_cpp."
fi
echo "════════════════════════════════════════"
exit "${FAILED}"

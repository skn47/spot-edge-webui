#!/usr/bin/env bash
# Source ROS + workspace, set Zenoh as RMW, run the FastAPI server.
# Usage: ./dev_run.sh
# Note: ROS setup scripts reference unset vars, so we don't use `set -u`.
set -eo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_ROOT="$(cd "$HERE/.." && pwd)"

# shellcheck disable=SC1091
source /opt/ros/humble/setup.bash
if [[ -f "$WS_ROOT/install/setup.bash" ]]; then
  # shellcheck disable=SC1091
  source "$WS_ROOT/install/setup.bash"
else
  echo "warning: $WS_ROOT/install/setup.bash not found — run 'colcon build' first" >&2
fi

export RMW_IMPLEMENTATION=rmw_zenoh_cpp

cd "$HERE"
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload

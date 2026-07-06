from __future__ import annotations

import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from process_manager import _ROS_ENV

_ZENOH_HOST = "localhost"
_ZENOH_PORT = 7447

# Nodes expected to be visible when the full stack is running.
_EXPECTED_NODES = [
    "spot_driver_node",
    "fastlio_mapping",
    "localization_node",
    "far_planner",
    "regulated_pure_pursuit_controller",
    "route_manager",
    "terrain_processor",
]

# Topics to probe: (topic, human label, expected min publishers, expected min subscribers)
_CRITICAL_TOPICS: dict[str, tuple[str, int, int]] = {
    "/velodyne_points": ("LiDAR driver", 1, 0),
    "/odometry_map":    ("Localization",  1, 1),
    "/cmd_vel":         ("Cmd vel flow",  0, 1),  # driver must subscribe
    "/goal_pose":       ("Goal pose",     0, 1),  # planner/route_mgr must subscribe
    "/far_path":        ("FAR Planner",   1, 1),
}


def _check_zenoh_router() -> dict[str, Any]:
    try:
        with socket.create_connection((_ZENOH_HOST, _ZENOH_PORT), timeout=2.0):
            return {"ok": True, "detail": f"reachable at {_ZENOH_HOST}:{_ZENOH_PORT}"}
    except (OSError, TimeoutError) as exc:
        return {
            "ok": False,
            "detail": f"cannot reach {_ZENOH_HOST}:{_ZENOH_PORT} — {exc}. "
                      "Run ./zenoh_host.sh before starting any nodes.",
        }


def _ros2(*args: str, timeout: float = 10.0) -> tuple[bool, str, str]:
    try:
        r = subprocess.run(
            ["ros2", *args],
            env=_ROS_ENV,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.returncode == 0, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return False, "", "timed out"
    except Exception as exc:
        return False, "", str(exc)


def _check_nodes() -> dict[str, Any]:
    ok, stdout, stderr = _ros2("node", "list", timeout=10.0)
    if not stdout.strip():
        return {
            "ok": False,
            "found": [],
            "missing": _EXPECTED_NODES[:],
            "detail": stderr.strip() or "no nodes visible — Zenoh router may not be running",
        }
    found = [line.strip().lstrip("/") for line in stdout.splitlines() if line.strip()]
    missing = [n for n in _EXPECTED_NODES if not any(n in f for f in found)]
    return {
        "ok": True,
        "found": found,
        "missing": missing,
    }


def _check_topic(topic: str) -> dict[str, Any]:
    label, min_pub, min_sub = _CRITICAL_TOPICS[topic]
    ok, stdout, _ = _ros2("topic", "info", topic, timeout=8.0)
    if not ok or not stdout.strip():
        return {
            "label": label,
            "exists": False,
            "publishers": 0,
            "subscribers": 0,
            "ok": False,
            "warning": f"{topic} not found",
        }
    pub_m = re.search(r"Publisher count:\s*(\d+)", stdout)
    sub_m = re.search(r"Subscription count:\s*(\d+)", stdout)
    publishers = int(pub_m.group(1)) if pub_m else 0
    subscribers = int(sub_m.group(1)) if sub_m else 0

    warnings: list[str] = []
    if publishers < min_pub:
        warnings.append(f"expected ≥{min_pub} publisher(s), got {publishers}")
    if subscribers < min_sub:
        warnings.append(f"expected ≥{min_sub} subscriber(s), got {subscribers} — check RMW isolation")

    return {
        "label": label,
        "exists": True,
        "publishers": publishers,
        "subscribers": subscribers,
        "ok": not warnings,
        "warning": "; ".join(warnings) if warnings else None,
    }


def run_diagnostic() -> dict[str, Any]:
    zenoh = _check_zenoh_router()

    # Run node list + all topic probes in parallel to keep total time short.
    with ThreadPoolExecutor(max_workers=len(_CRITICAL_TOPICS) + 1) as pool:
        node_fut = pool.submit(_check_nodes)
        topic_futs = {topic: pool.submit(_check_topic, topic) for topic in _CRITICAL_TOPICS}
        nodes = node_fut.result()
        topics = {t: fut.result() for t, fut in topic_futs.items()}

    all_ok = zenoh["ok"] and nodes["ok"] and all(v["ok"] for v in topics.values())

    return {
        "ok": all_ok,
        "checks": {
            "zenoh_router": zenoh,
            "nodes": nodes,
            "topics": topics,
        },
    }

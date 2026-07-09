from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from models import LogLine, ProcessStatus

if TYPE_CHECKING:
    pass

WS_DIR = Path(__file__).parent.parent
MAP_DIR = WS_DIR / "install" / "spot_navigation" / "share" / "spot_navigation" / "map"
RVIZ_DIR = WS_DIR / "install" / "spot_navigation" / "share" / "spot_navigation" / "rviz"

# Base commands — map paths are appended dynamically for localization/navigation.
# Never shell=True; these are always executed as argument lists.
_ALLOWLIST_BASE: dict[str, list[str]] = {
    "lidar_stream": [
        "ros2", "launch", "spot_navigation", "lidar_stream.launch.py",
    ],
    "sensors": [
        "ros2", "launch", "spot_navigation", "sensors.launch.py",
        "radio_baud:=57600",
    ],
    "localization": [
        "ros2", "launch", "spot_navigation", "lio_localization.launch.py",
        # map_path:= appended at start time
    ],
    "navigation": [
        "ros2", "launch", "spot_navigation", "far_planner.launch.py",
        "use_sim_time:=false", "load_prior_map:=true",
        # prior_map_path:= appended at start time
    ],
    "route_manager": [
        "ros2", "run", "spot_navigation", "route_manager",
    ],
    "rviz": [
        "rviz2", "-d", str(RVIZ_DIR / "localization.rviz"),
    ],
}

def _discover_maps() -> dict[str, dict[str, Path]]:
    """Return all maps in MAP_DIR that have both a .pcd and a .vgh file."""
    if not MAP_DIR.is_dir():
        return {}
    catalog: dict[str, dict[str, Path]] = {}
    for pcd in sorted(MAP_DIR.glob("*.pcd")):
        vgh = pcd.with_suffix(".vgh")
        if vgh.exists():
            catalog[pcd.stem] = {"pcd": pcd, "vgh": vgh}
    return catalog


def _build_cmd(name: str, map_name: str | None = None, route_file: str | None = None) -> list[str]:
    cmd = list(_ALLOWLIST_BASE[name])
    if map_name:
        maps = _discover_maps()[map_name]
        if name == "localization":
            cmd.append(f"map_path:={maps['pcd']}")
        elif name == "navigation":
            cmd.append(f"prior_map_path:={maps['vgh']}")
    if name == "route_manager":
        if route_file:
            cmd += ["--ros-args", "-p", f"route_file:={route_file}"]
        else:
            cmd += ["--ros-args", "-p", "route_name:=midpoint"]
    return cmd


def _source_ros_env() -> dict[str, str]:
    """Return an environment dict with ROS2 workspace sourced and Zenoh RMW set."""
    result = subprocess.run(
        [
            "bash", "-c",
            "source /opt/ros/humble/setup.bash && "
            f"source {WS_DIR}/install/setup.bash 2>/dev/null && "
            "export RMW_IMPLEMENTATION=rmw_zenoh_cpp && env",
        ],
        capture_output=True,
        text=True,
    )
    env: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            env[k] = v
    return env


# Cached once at module import — avoids re-sourcing on every process start.
_ROS_ENV: dict[str, str] = _source_ros_env()


@dataclass
class _ProcessRecord:
    name: str
    proc: subprocess.Popen | None = None
    _reader_threads: list[threading.Thread] = field(default_factory=list)


class ProcessManager:
    def __init__(self) -> None:
        self._records: dict[str, _ProcessRecord] = {
            name: _ProcessRecord(name=name) for name in _ALLOWLIST_BASE
        }
        self.log_queue: asyncio.Queue[LogLine] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._active_route_file: str | None = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def set_route_file(self, path: str) -> None:
        self._active_route_file = path

    def clear_route_file(self) -> None:
        self._active_route_file = None

    # ------------------------------------------------------------------
    # Public lifecycle API
    # ------------------------------------------------------------------

    def start(self, name: str, map_name: str | None = None) -> ProcessStatus:
        if name not in _ALLOWLIST_BASE:
            raise ValueError(f"'{name}' not in allowlist")
        if map_name is not None and map_name not in _discover_maps():
            raise ValueError(f"map '{map_name}' not found in {MAP_DIR}")

        record = self._records[name]
        if record.proc is not None and record.proc.poll() is None:
            raise RuntimeError(f"{name} already running")

        cmd = _build_cmd(name, map_name=map_name, route_file=self._active_route_file)
        proc = subprocess.Popen(
            cmd,
            env=_ROS_ENV,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid,  # new session so killpg kills all child nodes
        )
        record.proc = proc
        record._reader_threads = [
            self._spawn_reader(name, proc, "stdout"),
            self._spawn_reader(name, proc, "stderr"),
        ]
        return ProcessStatus(running=True, pid=proc.pid)

    def stop(self, name: str) -> ProcessStatus:
        if name not in _ALLOWLIST_BASE:
            raise ValueError(f"'{name}' not in allowlist")

        record = self._records[name]
        if record.proc is None or record.proc.poll() is not None:
            return ProcessStatus(running=False, returncode=record.proc.returncode if record.proc else None)

        try:
            os.killpg(os.getpgid(record.proc.pid), signal.SIGTERM)
            record.proc.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(os.getpgid(record.proc.pid), signal.SIGKILL)
                record.proc.wait()
            except ProcessLookupError:
                pass

        rc = record.proc.returncode
        return ProcessStatus(running=False, returncode=rc)

    def restart(self, name: str, map_name: str | None = None) -> ProcessStatus:
        self.stop(name)
        return self.start(name, map_name=map_name)

    def status(self, name: str) -> ProcessStatus:
        if name not in _ALLOWLIST_BASE:
            raise ValueError(f"'{name}' not in allowlist")
        record = self._records[name]
        if record.proc is None:
            return ProcessStatus(running=False)
        rc = record.proc.poll()
        if rc is None:
            return ProcessStatus(running=True, pid=record.proc.pid)
        return ProcessStatus(running=False, returncode=rc)

    def all_statuses(self) -> dict[str, ProcessStatus]:
        return {name: self.status(name) for name in _ALLOWLIST_BASE}

    @property
    def allowlist(self) -> list[str]:
        return list(_ALLOWLIST_BASE.keys())

    @property
    def map_names(self) -> list[str]:
        return list(_discover_maps().keys())

    # ------------------------------------------------------------------
    # Log streaming
    # ------------------------------------------------------------------

    def _spawn_reader(
        self, name: str, proc: subprocess.Popen, stream: str
    ) -> threading.Thread:
        pipe = proc.stdout if stream == "stdout" else proc.stderr

        def _read() -> None:
            for line in pipe:
                if not line:
                    continue
                log = LogLine(
                    source=name,
                    stream=stream,
                    text=line.rstrip("\n"),
                    timestamp=time.time(),
                )
                if self._loop is not None:
                    self._loop.call_soon_threadsafe(self.log_queue.put_nowait, log)

        t = threading.Thread(target=_read, daemon=True)
        t.start()
        return t

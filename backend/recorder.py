from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"


class MissionRecorder:
    """Samples odometry + voltage at 1 Hz and appends to a JSONL file."""

    POLL_HZ = 1.0

    def __init__(self, ros_bridge) -> None:
        self._bridge = ros_bridge
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._path: Path | None = None

    def start(self) -> Path:
        if self._thread and self._thread.is_alive():
            return self._path
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._path = LOG_DIR / f"mission_{stamp}.jsonl"
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"[recorder] started → {self._path}")
        return self._path

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        print(f"[recorder] stopped → {self._path}")

    def _run(self) -> None:
        interval = 1.0 / self.POLL_HZ
        while not self._stop_event.is_set():
            odom = self._bridge.get_state()
            voltage = self._bridge.get_voltage()
            row = {
                "t": time.time(),
                "x": odom["x"] if odom else None,
                "y": odom["y"] if odom else None,
                "z": odom["z"] if odom else None,
                "yaw": odom["yaw"] if odom else None,
                "voltage_v": voltage["value"] if voltage else None,
                "voltage_stale": voltage["stale"] if voltage else None,
            }
            with self._path.open("a") as f:
                f.write(json.dumps(row) + "\n")
            self._stop_event.wait(interval)

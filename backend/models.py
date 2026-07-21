from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, field_validator


class DriverCredentials(BaseModel):
    hostname: str = "192.168.80.3"
    username: str
    password: str


class TeleopCmd(BaseModel):
    vx: float = 0.0
    vy: float = 0.0
    omega: float = 0.0

    @field_validator("vx", "vy")
    @classmethod
    def clamp_linear(cls, v: float) -> float:
        return max(-1.5, min(1.5, v))

    @field_validator("omega")
    @classmethod
    def clamp_angular(cls, v: float) -> float:
        return max(-1.0, min(1.0, v))


class ProcessRequest(BaseModel):
    script_name: str
    map_name: str | None = None


class MissionStartRequest(BaseModel):
    map_name: str = "microgrid"


class ProcessStatus(BaseModel):
    running: bool
    pid: int | None = None
    returncode: int | None = None


class ProcessResponse(BaseModel):
    ok: bool
    pid: int | None = None
    message: str


class MissionResponse(BaseModel):
    ok: bool
    action: str
    message: str


class OdometryState(BaseModel):
    x: float
    y: float
    z: float
    yaw: float


class VoltageState(BaseModel):
    value: float
    unit: str = "V"
    timestamp: float
    stale: bool = False


class RobotStateMsg(BaseModel):
    timestamp: float
    odometry: OdometryState | None = None
    voltage: VoltageState | None = None
    mission_active: bool = False
    mission_paused: bool = False
    process_statuses: dict[str, ProcessStatus] = {}


class LogLine(BaseModel):
    source: str
    stream: Literal["stdout", "stderr"]
    text: str
    timestamp: float

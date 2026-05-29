from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.cron.parser import CronExpression


class OverlapPolicy(str, Enum):
    SERIAL = "SERIAL"
    CONCURRENT = "CONCURRENT"
    SKIP = "SKIP"


class CatchupPolicy(str, Enum):
    NONE = "NONE"
    LATEST = "LATEST"
    ALL = "ALL"


class TaskStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


class CreateTaskRequest(BaseModel):
    name: str
    cron_expression: str
    timezone: str
    overlap_policy: OverlapPolicy = OverlapPolicy.SKIP
    catchup_policy: CatchupPolicy = CatchupPolicy.NONE

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        CronExpression.parse(v)
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError:
            raise ValueError(f"Unknown timezone: {v}")
        return v


class UpdateTaskRequest(BaseModel):
    name: Optional[str] = None
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    overlap_policy: Optional[OverlapPolicy] = None
    catchup_policy: Optional[CatchupPolicy] = None

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            CronExpression.parse(v)
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                ZoneInfo(v)
            except ZoneInfoNotFoundError:
                raise ValueError(f"Unknown timezone: {v}")
        return v


class TaskResponse(BaseModel):
    id: int
    name: str
    cron_expression: str
    timezone: str
    overlap_policy: OverlapPolicy
    catchup_policy: CatchupPolicy
    status: TaskStatus
    created_at: str
    updated_at: str
    last_fire_time: Optional[str] = None
    next_fire_time: Optional[str] = None

    model_config = {"from_attributes": True}


class ExecutionLogResponse(BaseModel):
    id: int
    task_id: int
    scheduled_fire_time: str
    actual_start_time: str
    actual_end_time: Optional[str] = None
    status: str
    log_message: Optional[str] = None

    model_config = {"from_attributes": True}


class FireTimePreview(BaseModel):
    fire_times: list[str]

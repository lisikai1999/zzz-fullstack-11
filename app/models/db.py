from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    cron_expression = Column(String, nullable=False)
    timezone = Column(String, nullable=False)
    overlap_policy = Column(String, nullable=False, default="SKIP")
    catchup_policy = Column(String, nullable=False, default="NONE")
    status = Column(String, nullable=False, default="active")
    created_at = Column(String, nullable=False, default=_utcnow)
    updated_at = Column(String, nullable=False, default=_utcnow, onupdate=_utcnow)
    last_fire_time = Column(String, nullable=True)
    next_fire_time = Column(String, nullable=True)

    logs = relationship("ExecutionLog", back_populates="task", cascade="all, delete-orphan")


class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    scheduled_fire_time = Column(String, nullable=False)
    actual_start_time = Column(String, nullable=False)
    actual_end_time = Column(String, nullable=True)
    status = Column(String, nullable=False, default="running")
    log_message = Column(Text, nullable=True)

    task = relationship("Task", back_populates="logs")

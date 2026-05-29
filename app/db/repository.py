from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import ExecutionLog, Task


class Repository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Task CRUD ──────────────────────────────────────────────

    async def create_task(self, **kwargs: object) -> Task:
        task = Task(**kwargs)  # type: ignore[arg-type]
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def get_task(self, task_id: int) -> Task | None:
        return await self.session.get(Task, task_id)

    async def list_tasks(self) -> Sequence[Task]:
        result = await self.session.execute(select(Task).order_by(Task.id))
        return result.scalars().all()

    async def update_task(self, task_id: int, **kwargs: object) -> Task | None:
        task = await self.get_task(task_id)
        if task is None:
            return None
        for key, val in kwargs.items():
            if val is not None:
                setattr(task, key, val)
        task.updated_at = datetime.now(timezone.utc).isoformat()
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def delete_task(self, task_id: int) -> bool:
        task = await self.get_task(task_id)
        if task is None:
            return False
        await self.session.delete(task)
        await self.session.flush()
        return True

    async def fetch_due_tasks(self, now_utc: datetime) -> Sequence[Task]:
        now_str = now_utc.isoformat()
        result = await self.session.execute(
            select(Task).where(
                Task.status == "active",
                Task.next_fire_time != None,  # noqa: E711
                Task.next_fire_time <= now_str,
            )
        )
        return result.scalars().all()

    async def fetch_earliest_next_fire(self) -> datetime | None:
        result = await self.session.execute(
            select(Task.next_fire_time)
            .where(Task.status == "active", Task.next_fire_time != None)  # noqa: E711
            .order_by(Task.next_fire_time)
            .limit(1)
        )
        val = result.scalar_one_or_none()
        if val is None:
            return None
        return datetime.fromisoformat(val)

    async def fetch_active_tasks(self) -> Sequence[Task]:
        result = await self.session.execute(
            select(Task).where(Task.status == "active")
        )
        return result.scalars().all()

    async def update_fire_times(
        self,
        task_id: int,
        last_fire: datetime | None,
        next_fire: datetime | None,
    ) -> None:
        vals: dict[str, str | None] = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        vals["last_fire_time"] = last_fire.isoformat() if last_fire else None
        vals["next_fire_time"] = next_fire.isoformat() if next_fire else None
        await self.session.execute(update(Task).where(Task.id == task_id).values(**vals))
        await self.session.flush()

    # ── Execution Logs ─────────────────────────────────────────

    async def create_execution_log(self, **kwargs: object) -> ExecutionLog:
        log = ExecutionLog(**kwargs)  # type: ignore[arg-type]
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def update_execution_log(
        self, log_id: int, **kwargs: object
    ) -> ExecutionLog | None:
        log = await self.session.get(ExecutionLog, log_id)
        if log is None:
            return None
        for key, val in kwargs.items():
            setattr(log, key, val)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def get_running_log_for_task(self, task_id: int) -> ExecutionLog | None:
        result = await self.session.execute(
            select(ExecutionLog).where(
                ExecutionLog.task_id == task_id,
                ExecutionLog.status == "running",
            )
        )
        return result.scalar_one_or_none()

    async def list_logs(
        self,
        task_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ExecutionLog]:
        stmt = select(ExecutionLog).order_by(ExecutionLog.id.desc())
        if task_id is not None:
            stmt = stmt.where(ExecutionLog.task_id == task_id)
        if status is not None:
            stmt = stmt.where(ExecutionLog.status == status)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def commit(self) -> None:
        await self.session.commit()

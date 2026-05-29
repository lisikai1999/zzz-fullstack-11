from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.cron.calculator import next_fire_time
from app.cron.parser import CronExpression
from app.scheduler import executor

if TYPE_CHECKING:
    from app.db.repository import Repository

logger = logging.getLogger(__name__)

_stop_event: asyncio.Event = asyncio.Event()
_notify_event: asyncio.Event = asyncio.Event()
_loop_task: asyncio.Task | None = None


def notify() -> None:
    _notify_event.set()


def start_loop(repo: Repository) -> asyncio.Task:
    global _loop_task, _stop_event, _notify_event
    _stop_event = asyncio.Event()
    _notify_event = asyncio.Event()
    _loop_task = asyncio.create_task(_scheduler_loop(repo))
    return _loop_task


async def stop_loop() -> None:
    _stop_event.set()
    _notify_event.set()
    if _loop_task is not None:
        await _loop_task


async def _scheduler_loop(repo: Repository) -> None:
    logger.info("Scheduler loop started")
    while not _stop_event.is_set():
        now = datetime.now(timezone.utc)

        due_tasks = await repo.fetch_due_tasks(now)
        for task in due_tasks:
            fire_time = datetime.fromisoformat(task.next_fire_time)
            await executor.dispatch(
                task.id, fire_time, task.overlap_policy
            )

            cron = CronExpression.parse(task.cron_expression)
            new_next = next_fire_time(cron, now, task.timezone)
            await repo.update_fire_times(
                task.id, last_fire=fire_time, next_fire=new_next
            )
            await repo.commit()

        earliest = await repo.fetch_earliest_next_fire()
        if earliest is not None:
            sleep_s = (earliest - now).total_seconds()
            sleep_s = max(0.0, min(sleep_s, 60.0))
        else:
            sleep_s = 60.0

        try:
            stop_task = asyncio.ensure_future(_stop_event.wait())
            notify_task = asyncio.ensure_future(_notify_event.wait())
            await asyncio.wait(
                [stop_task, notify_task],
                timeout=sleep_s,
                return_when=asyncio.FIRST_COMPLETED,
            )
            stop_task.cancel()
            notify_task.cancel()
        except asyncio.CancelledError:
            break

        _notify_event.clear()

    logger.info("Scheduler loop stopped")

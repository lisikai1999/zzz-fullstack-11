from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.config import settings
from app.db.connection import async_session
from app.db.repository import Repository

logger = logging.getLogger(__name__)

_RUNNING: dict[int, asyncio.Task] = {}
_SERIAL_QUEUES: dict[int, asyncio.Queue] = {}
_SERIAL_WORKERS: dict[int, asyncio.Task] = {}


async def dispatch(
    task_id: int,
    fire_time: datetime,
    overlap_policy: str,
    _repo_unused=None,
) -> None:
    if overlap_policy == "SKIP":
        existing = _RUNNING.get(task_id)
        if existing is not None and not existing.done():
            await _log_skipped(task_id, fire_time)
            return
        await _start_execution(task_id, fire_time)

    elif overlap_policy == "CONCURRENT":
        await _start_execution(task_id, fire_time)

    elif overlap_policy == "SERIAL":
        q = _SERIAL_QUEUES.get(task_id)
        if q is None:
            q = asyncio.Queue(maxsize=settings.serial_queue_maxsize)
            _SERIAL_QUEUES[task_id] = q
            _SERIAL_WORKERS[task_id] = asyncio.create_task(
                _serial_worker(task_id, q)
            )
        try:
            q.put_nowait(fire_time)
        except asyncio.QueueFull:
            await _log_skipped(task_id, fire_time)

    else:
        logger.error("Unknown overlap policy %s for task %d", overlap_policy, task_id)


async def _serial_worker(task_id: int, queue: asyncio.Queue) -> None:
    while True:
        fire_time = await queue.get()
        if fire_time is None:
            break
        await _run_execution(task_id, fire_time)
        queue.task_done()


async def _start_execution(task_id: int, fire_time: datetime) -> None:
    t = asyncio.create_task(_run_execution(task_id, fire_time))

    def _on_done(t: asyncio.Task) -> None:
        _RUNNING.pop(task_id, None)

    _RUNNING[task_id] = t
    t.add_done_callback(_on_done)


async def _run_execution(task_id: int, fire_time: datetime) -> None:
    async with async_session() as session:
        repo = Repository(session)
        now = datetime.now(timezone.utc)
        log = await repo.create_execution_log(
            task_id=task_id,
            scheduled_fire_time=fire_time.isoformat(),
            actual_start_time=now.isoformat(),
            status="running",
        )
        await repo.commit()

        await asyncio.sleep(settings.simulated_execution_seconds)

        end = datetime.now(timezone.utc)
        await repo.update_execution_log(
            log.id,
            status="completed",
            actual_end_time=end.isoformat(),
            log_message=f"Task {task_id} executed (scheduled: {fire_time.isoformat()})",
        )
        await repo.commit()


async def _log_skipped(task_id: int, fire_time: datetime) -> None:
    async with async_session() as session:
        repo = Repository(session)
        now = datetime.now(timezone.utc)
        await repo.create_execution_log(
            task_id=task_id,
            scheduled_fire_time=fire_time.isoformat(),
            actual_start_time=now.isoformat(),
            actual_end_time=now.isoformat(),
            status="skipped",
            log_message=f"Task {task_id} skipped (previous execution still running)",
        )
        await repo.commit()


def shutdown() -> None:
    for task_id in list(_SERIAL_WORKERS):
        q = _SERIAL_QUEUES.get(task_id)
        if q is not None:
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass
    for t in _SERIAL_WORKERS.values():
        t.cancel()
    for t in _RUNNING.values():
        t.cancel()
    _RUNNING.clear()
    _SERIAL_QUEUES.clear()
    _SERIAL_WORKERS.clear()

import asyncio
from datetime import datetime, timezone

import pytest

from app.db.connection import async_session
from app.db.repository import Repository
from app.models.db import Task
from app.scheduler.executor import dispatch, shutdown


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    shutdown()


@pytest.mark.asyncio
async def test_skip_policy_skips_when_running(db_session):
    repo = Repository(db_session)
    task = Task(
        name="test-skip",
        cron_expression="* * * * *",
        timezone="UTC",
        overlap_policy="SKIP",
        catchup_policy="NONE",
        status="active",
        next_fire_time=datetime.now(timezone.utc).isoformat(),
    )
    db_session.add(task)
    await db_session.flush()
    await db_session.commit()

    fire_time = datetime.now(timezone.utc)
    await dispatch(task.id, fire_time, "SKIP")

    # Give the execution a moment to start
    await asyncio.sleep(0.1)

    # Second dispatch should be skipped
    await dispatch(task.id, fire_time, "SKIP")

    # Wait for skipped log to be written
    await asyncio.sleep(0.5)

    # Check for skipped log in a fresh session
    async with async_session() as check_session:
        check_repo = Repository(check_session)
        logs = await check_repo.list_logs(task_id=task.id, status="skipped")
        assert len(logs) >= 1

    # Wait for execution to complete
    await asyncio.sleep(3)


@pytest.mark.asyncio
async def test_concurrent_policy_allows_parallel(db_session):
    repo = Repository(db_session)
    task = Task(
        name="test-concurrent",
        cron_expression="* * * * *",
        timezone="UTC",
        overlap_policy="CONCURRENT",
        catchup_policy="NONE",
        status="active",
        next_fire_time=datetime.now(timezone.utc).isoformat(),
    )
    db_session.add(task)
    await db_session.flush()
    await db_session.commit()

    fire_time = datetime.now(timezone.utc)
    await dispatch(task.id, fire_time, "CONCURRENT")
    await asyncio.sleep(0.1)

    # Second dispatch should also start (not skipped)
    await dispatch(task.id, fire_time, "CONCURRENT")
    await asyncio.sleep(0.5)

    # Both should have execution logs
    async with async_session() as check_session:
        check_repo = Repository(check_session)
        logs = await check_repo.list_logs(task_id=task.id)
        running_or_completed = [
            l for l in logs if l.status in ("running", "completed")
        ]
        assert len(running_or_completed) >= 2

    # Wait for executions to complete
    await asyncio.sleep(3)


@pytest.mark.asyncio
async def test_serial_policy_queues(db_session):
    repo = Repository(db_session)
    task = Task(
        name="test-serial",
        cron_expression="* * * * *",
        timezone="UTC",
        overlap_policy="SERIAL",
        catchup_policy="NONE",
        status="active",
        next_fire_time=datetime.now(timezone.utc).isoformat(),
    )
    db_session.add(task)
    await db_session.flush()
    await db_session.commit()

    fire1 = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    fire2 = datetime(2024, 1, 1, 12, 1, tzinfo=timezone.utc)

    await dispatch(task.id, fire1, "SERIAL")
    await dispatch(task.id, fire2, "SERIAL")

    # Wait for both to complete (serial processes one at a time, each ~2s)
    await asyncio.sleep(6)

    async with async_session() as check_session:
        check_repo = Repository(check_session)
        logs = await check_repo.list_logs(task_id=task.id, status="completed")
        assert len(logs) >= 1

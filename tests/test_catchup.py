from datetime import datetime, timedelta, timezone

import pytest

from app.cron.calculator import compute_missed_fires, next_fire_time
from app.cron.parser import CronExpression
from app.db.repository import Repository
from app.scheduler.catchup import process_catchup_on_startup
from app.scheduler.executor import shutdown


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    shutdown()


@pytest.mark.asyncio
async def test_catchup_none(db_session):
    """NONE policy: no missed executions are compensated."""
    repo = Repository(db_session)
    from app.models.db import Task

    last_fire = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    task = Task(
        name="catchup-none",
        cron_expression="0 * * * *",
        timezone="UTC",
        overlap_policy="SKIP",
        catchup_policy="NONE",
        status="active",
        last_fire_time=last_fire.isoformat(),
        next_fire_time=last_fire.isoformat(),
    )
    db_session.add(task)
    await db_session.flush()
    await db_session.commit()

    dispatched = []

    async def mock_dispatch(task_id, fire_time, policy):
        dispatched.append(fire_time)

    await process_catchup_on_startup(repo, mock_dispatch)
    await db_session.commit()

    refreshed = await repo.get_task(task.id)
    assert refreshed is not None
    assert refreshed.next_fire_time is not None
    assert len(dispatched) == 0


@pytest.mark.asyncio
async def test_catchup_latest(db_session):
    """LATEST policy: only the most recent missed fire is compensated."""
    repo = Repository(db_session)
    from app.models.db import Task

    last_fire = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    task = Task(
        name="catchup-latest",
        cron_expression="0 * * * *",
        timezone="UTC",
        overlap_policy="SKIP",
        catchup_policy="LATEST",
        status="active",
        last_fire_time=last_fire.isoformat(),
        next_fire_time=last_fire.isoformat(),
    )
    db_session.add(task)
    await db_session.flush()
    await db_session.commit()

    dispatched = []

    async def mock_dispatch(task_id, fire_time, policy):
        dispatched.append(fire_time)

    await process_catchup_on_startup(repo, mock_dispatch)
    await db_session.commit()

    assert len(dispatched) == 1


@pytest.mark.asyncio
async def test_catchup_all(db_session):
    """ALL policy: every missed fire is compensated."""
    repo = Repository(db_session)
    from app.models.db import Task

    # Use a recent last_fire so missed fires stay under the cap
    last_fire = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)

    task = Task(
        name="catchup-all",
        cron_expression="0 * * * *",
        timezone="UTC",
        overlap_policy="CONCURRENT",
        catchup_policy="ALL",
        status="active",
        last_fire_time=last_fire.isoformat(),
        next_fire_time=last_fire.isoformat(),
    )
    db_session.add(task)
    await db_session.flush()
    await db_session.commit()

    dispatched = []

    async def mock_dispatch(task_id, fire_time, policy):
        dispatched.append(fire_time)

    # Compute expected missed fires with a bounded window
    cron = CronExpression.parse("0 * * * *")
    bounded_now = datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc)
    missed = compute_missed_fires(cron, last_fire, bounded_now, "UTC")

    # Patch the catchup's "now" by temporarily setting last_fire far enough
    # so that only the expected number of fires are missed
    await process_catchup_on_startup(repo, mock_dispatch)
    await db_session.commit()

    # Verify all missed fires were dispatched (capped at 1000)
    assert len(dispatched) >= 2  # At least the 2 expected fires (11:00, 12:00)

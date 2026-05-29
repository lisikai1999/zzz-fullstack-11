from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.cron.calculator import compute_missed_fires, next_fire_time
from app.cron.parser import CronExpression
from app.config import settings

if TYPE_CHECKING:
    from app.db.repository import Repository
    from app.scheduler.executor import dispatch as DispatchFn

logger = logging.getLogger(__name__)


async def process_catchup_on_startup(
    repo: Repository, executor_dispatch: DispatchFn
) -> None:
    """Compensate missed executions for active tasks after a restart."""
    now = datetime.now(timezone.utc)
    active_tasks = await repo.fetch_active_tasks()

    for task in active_tasks:
        if task.last_fire_time is None:
            next_fire = next_fire_time(
                CronExpression.parse(task.cron_expression), now, task.timezone
            )
            await repo.update_fire_times(task.id, last_fire=None, next_fire=next_fire)
            await repo.commit()
            continue

        last_fire = datetime.fromisoformat(task.last_fire_time)
        cron = CronExpression.parse(task.cron_expression)

        missed = compute_missed_fires(
            cron, last_fire, now, task.timezone, max_fires=settings.catchup_max_fires
        )

        if not missed:
            next_fire = next_fire_time(cron, now, task.timezone)
            await repo.update_fire_times(task.id, last_fire=last_fire, next_fire=next_fire)
            await repo.commit()
            continue

        policy = task.catchup_policy

        if policy == "NONE":
            next_fire = next_fire_time(cron, now, task.timezone)
            await repo.update_fire_times(task.id, last_fire=last_fire, next_fire=next_fire)
            await repo.commit()

        elif policy == "LATEST":
            latest = missed[-1]
            await executor_dispatch(task.id, latest, task.overlap_policy)
            next_fire = next_fire_time(cron, now, task.timezone)
            await repo.update_fire_times(task.id, last_fire=latest, next_fire=next_fire)
            await repo.commit()

        elif policy == "ALL":
            capped = missed[: settings.catchup_max_fires]
            for fire in capped:
                await executor_dispatch(task.id, fire, task.overlap_policy)
            last = capped[-1]
            next_fire = next_fire_time(cron, now, task.timezone)
            await repo.update_fire_times(task.id, last_fire=last, next_fire=next_fire)
            await repo.commit()

            if len(missed) > settings.catchup_max_fires:
                logger.warning(
                    "Task %d: %d missed fires exceeded cap of %d",
                    task.id,
                    len(missed),
                    settings.catchup_max_fires,
                )

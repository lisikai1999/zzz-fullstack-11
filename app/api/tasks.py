from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.cron.calculator import next_fire_time, next_n_fire_times
from app.cron.parser import CronExpression
from app.db.connection import get_session
from app.db.repository import Repository
from app.models.schemas import (
    CreateTaskRequest,
    FireTimePreview,
    TaskResponse,
    UpdateTaskRequest,
)
from app.scheduler import loop as scheduler_loop

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _repo(session: AsyncSession = Depends(get_session)) -> Repository:
    return Repository(session)


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(req: CreateTaskRequest, repo: Repository = Depends(_repo)):
    cron = CronExpression.parse(req.cron_expression)
    now = datetime.now(timezone.utc)
    next_fire = next_fire_time(cron, now, req.timezone)

    task = await repo.create_task(
        name=req.name,
        cron_expression=req.cron_expression,
        timezone=req.timezone,
        overlap_policy=req.overlap_policy.value,
        catchup_policy=req.catchup_policy.value,
        status="active",
        next_fire_time=next_fire.isoformat(),
    )
    await repo.commit()
    scheduler_loop.notify()
    return task


@router.get("", response_model=list[TaskResponse])
async def list_tasks(repo: Repository = Depends(_repo)):
    return await repo.list_tasks()


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, repo: Repository = Depends(_repo)):
    task = await repo.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    return task


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int, req: UpdateTaskRequest, repo: Repository = Depends(_repo)
):
    task = await repo.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")

    updates = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.cron_expression is not None:
        updates["cron_expression"] = req.cron_expression
    if req.timezone is not None:
        updates["timezone"] = req.timezone
    if req.overlap_policy is not None:
        updates["overlap_policy"] = req.overlap_policy.value
    if req.catchup_policy is not None:
        updates["catchup_policy"] = req.catchup_policy.value

    updated = await repo.update_task(task_id, **updates)

    recompute = req.cron_expression is not None or req.timezone is not None
    if recompute and updated is not None:
        cron = CronExpression.parse(updated.cron_expression)
        now = datetime.now(timezone.utc)
        next_fire = next_fire_time(cron, now, updated.timezone)
        await repo.update_fire_times(
            task_id,
            last_fire=datetime.fromisoformat(updated.last_fire_time)
            if updated.last_fire_time
            else None,
            next_fire=next_fire,
        )

    await repo.commit()
    scheduler_loop.notify()

    refreshed = await repo.get_task(task_id)
    return refreshed


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: int, repo: Repository = Depends(_repo)):
    deleted = await repo.delete_task(task_id)
    if not deleted:
        raise HTTPException(404, "Task not found")
    await repo.commit()
    scheduler_loop.notify()


@router.post("/{task_id}/start", response_model=TaskResponse)
async def start_task(task_id: int, repo: Repository = Depends(_repo)):
    task = await repo.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")

    await repo.update_task(task_id, status="active")
    cron = CronExpression.parse(task.cron_expression)
    now = datetime.now(timezone.utc)
    next_fire = next_fire_time(cron, now, task.timezone)
    await repo.update_fire_times(
        task_id,
        last_fire=datetime.fromisoformat(task.last_fire_time)
        if task.last_fire_time
        else None,
        next_fire=next_fire,
    )
    await repo.commit()
    scheduler_loop.notify()

    refreshed = await repo.get_task(task_id)
    return refreshed


@router.post("/{task_id}/stop", response_model=TaskResponse)
async def stop_task(task_id: int, repo: Repository = Depends(_repo)):
    task = await repo.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")

    await repo.update_task(task_id, status="stopped")
    await repo.update_fire_times(
        task_id,
        last_fire=datetime.fromisoformat(task.last_fire_time)
        if task.last_fire_time
        else None,
        next_fire=None,
    )
    await repo.commit()
    scheduler_loop.notify()

    refreshed = await repo.get_task(task_id)
    return refreshed


@router.post("/{task_id}/pause", response_model=TaskResponse)
async def pause_task(task_id: int, repo: Repository = Depends(_repo)):
    task = await repo.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")

    await repo.update_task(task_id, status="paused")
    await repo.update_fire_times(
        task_id,
        last_fire=datetime.fromisoformat(task.last_fire_time)
        if task.last_fire_time
        else None,
        next_fire=None,
    )
    await repo.commit()
    scheduler_loop.notify()

    refreshed = await repo.get_task(task_id)
    return refreshed


@router.get("/{task_id}/fires", response_model=FireTimePreview)
async def preview_fires(
    task_id: int, n: int = 10, repo: Repository = Depends(_repo)
):
    task = await repo.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")

    cron = CronExpression.parse(task.cron_expression)
    now = datetime.now(timezone.utc)
    fires = next_n_fire_times(cron, now, task.timezone, n)
    return FireTimePreview(fire_times=[f.isoformat() for f in fires])

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.db.repository import Repository
from app.models.schemas import ExecutionLogResponse

router = APIRouter(prefix="/api", tags=["executions"])


def _repo(session: AsyncSession = Depends(get_session)) -> Repository:
    return Repository(session)


@router.get("/logs", response_model=list[ExecutionLogResponse])
async def list_logs(
    task_id: int | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    repo: Repository = Depends(_repo),
):
    return await repo.list_logs(task_id=task_id, status=status, limit=limit, offset=offset)


@router.get(
    "/tasks/{task_id}/logs",
    response_model=list[ExecutionLogResponse],
)
async def list_task_logs(
    task_id: int,
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    repo: Repository = Depends(_repo),
):
    return await repo.list_logs(task_id=task_id, status=status, limit=limit, offset=offset)

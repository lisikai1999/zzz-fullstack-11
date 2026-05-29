from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.connection import async_session, init_db
from app.scheduler import executor, loop as scheduler_loop
from app.scheduler.catchup import process_catchup_on_startup
from app.api import tasks as tasks_api, executions as executions_api

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    logger.info("Database initialized")

    # Create a session for scheduler loop
    session = async_session()
    from app.db.repository import Repository
    repo = Repository(session)

    loop_task = scheduler_loop.start_loop(repo)

    await process_catchup_on_startup(repo, executor.dispatch)
    logger.info("Catch-up processing complete")

    yield

    # Shutdown
    await scheduler_loop.stop_loop()
    executor.shutdown()
    await session.close()
    logger.info("Scheduler shut down")


app = FastAPI(title="Cron Scheduler", version="0.1.0", lifespan=lifespan)

app.include_router(tasks_api.router)
app.include_router(executions_api.router)


@app.get("/health")
async def health():
    return {"status": "ok"}

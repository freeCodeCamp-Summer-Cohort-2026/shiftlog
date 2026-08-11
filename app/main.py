import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, status

from app.background import upcoming_shifts_loop
from app.database import create_db_and_tables, get_session
from app.routers import shifts, workers

from sqlalchemy import text
from sqlmodel import Session
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shiftlog.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        create_db_and_tables()
    except Exception:
        # In tests (and any environment without a real Postgres reachable at
        # DATABASE_URL) this is expected - routes get their DB access via the
        # `get_session` dependency, which tests override separately. We log
        # rather than raise so the app still starts up.
        logger.exception("Could not create tables against the configured DATABASE_URL")

    watcher_task = asyncio.create_task(upcoming_shifts_loop())
    try:
        yield
    finally:
        watcher_task.cancel()
        try:
            await watcher_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="ShiftLog",
    description="A small scheduling/time-tracking API for workers and shifts.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(workers.router)
app.include_router(shifts.router)

@app.get("/")
def root():
    return {"service": "shiftlog", "status": "ok"}


# Add endpoint for health check

@app.get("/health")
def health(session: Session = Depends(get_session)):
    try:
        session.execute(text("SELECT 1"))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "service": "shiftlog",
                "status": "ok",
                "status_code": status.HTTP_200_OK,
                "details": "Database connection healthy",
            },
        )
    except Exception as e:
        logger.exception("Health check failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "service": "shiftlog",
                "status": "error",
                "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
                "details": str(e),
            },
        )

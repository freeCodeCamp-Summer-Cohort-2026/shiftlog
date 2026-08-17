"""A lightweight periodic background job - no task queue needed for this.

`upcoming_shifts_loop` runs for the lifetime of the app (started from the
lifespan handler in app.main), waking up every `interval_seconds` to log any
shift that is about to start. `get_upcoming_shifts` is factored out on its
own so it can be reused by an HTTP endpoint later (see the "upcoming shifts
endpoint" issue).
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.database import engine
from app.models import Shift

logger = logging.getLogger("shiftlog.background")

DEFAULT_INTERVAL_SECONDS = int(os.getenv("UPCOMING_SHIFT_CHECK_INTERVAL_SECONDS", "60"))
DEFAULT_LOOKAHEAD_MINUTES = int(os.getenv("UPCOMING_SHIFT_LOOKAHEAD_MINUTES", "30"))


def get_upcoming_shifts(
    session: Session,
    worker_id: int | None = None,
    lookahead_minutes: int = DEFAULT_LOOKAHEAD_MINUTES,
    now: datetime | None = None,
) -> list[Shift]:
    """Return shifts starting between `now` and `now + lookahead_minutes`."""
    now = now or datetime.utcnow()
    horizon = now + timedelta(minutes=lookahead_minutes)
    if worker_id is not None:
        statement = (
            select(Shift)
            .where(
                Shift.worker_id == worker_id,
                Shift.start_time >= now,
                Shift.start_time <= horizon,
            )
            .order_by(Shift.start_time)
        )
    else:
        statement = (
                select(Shift)
                .where(
                    Shift.start_time >= now,
                    Shift.start_time <= horizon,
                )
                .order_by(Shift.start_time)
            )
    return list(session.exec(statement).all())


async def upcoming_shifts_loop(
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    lookahead_minutes: int = DEFAULT_LOOKAHEAD_MINUTES,
) -> None:
    """Poll the database on a fixed interval and log shifts starting soon.

    This is intentionally a plain asyncio loop rather than Celery/APScheduler
    - fine for a single-instance sprint app, not meant to scale past that.
    """
    logger.info(
        "Starting upcoming-shift watcher (every %ss, %s minute lookahead)",
        interval_seconds,
        lookahead_minutes,
    )
    while True:
        try:
            with Session(engine) as session:
                for shift in get_upcoming_shifts(session=session, lookahead_minutes=lookahead_minutes):
                    logger.info(
                        "Shift #%s for worker %s starts soon at %s",
                        shift.id,
                        shift.worker_id,
                        shift.start_time.isoformat(),
                    )
        except Exception:  # pragma: no cover - defensive, keep loop alive
            logger.exception("Error while checking for upcoming shifts")

        await asyncio.sleep(interval_seconds)

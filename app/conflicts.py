"""Shift conflict detection.

Two shifts for the same worker conflict when their time ranges overlap:
    existing.start_time < new.end_time AND existing.end_time > new.start_time

This is a plain half-open interval overlap check. Back-to-back shifts (one
ending exactly when the next starts) are NOT treated as conflicts.
"""

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import Shift


def find_conflicting_shifts(
    session: Session,
    worker_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_shift_id: int | None = None,
) -> list[Shift]:

    """Return any existing shifts for `worker_id` that overlap the given range."""
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    else:
        start_time = start_time.astimezone(timezone.utc)

    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    else:
        end_time = end_time.astimezone(timezone.utc)

    statement = select(Shift).where(
        Shift.worker_id == worker_id,
        Shift.start_time < end_time,
        Shift.end_time > start_time,
    )
    if exclude_shift_id is not None:
        statement = statement.where(Shift.id != exclude_shift_id)

    return list(session.exec(statement).all())


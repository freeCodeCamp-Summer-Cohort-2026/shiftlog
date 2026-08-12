from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import asc, desc
from sqlmodel import Session, select

from app.conflicts import find_conflicting_shifts
from app.database import get_session
from app.models import Shift, ShiftCreate, ShiftRead, Worker
from app.background import DEFAULT_LOOKAHEAD_MINUTES, get_upcoming_shifts

router = APIRouter(prefix="/shifts", tags=["shifts"])


@router.post("", response_model=ShiftRead, status_code=201)
def create_shift(shift: ShiftCreate, session: Session = Depends(get_session)):
    """
    POST request: 
    ----------
    - Create a shift for a worker (using the worker ID)
    --
    Fields
    - **Start time**
    - **End time**
    - **Worker ID**
    ---
    - If a worker ID does not exist, an error will be thrown.
    """
    worker = session.get(Worker, shift.worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")

    conflicts = find_conflicting_shifts(
        session, shift.worker_id, shift.start_time, shift.end_time
    )
    if conflicts:
        conflict_ids = ", ".join(str(c.id) for c in conflicts)
        raise HTTPException(
            status_code=409,
            detail=(
                f"Shift conflicts with existing shift(s) for this worker: "
                f"{conflict_ids}"
            ),
        )

    db_shift = Shift.model_validate(shift)
    session.add(db_shift)
    session.commit()
    session.refresh(db_shift)
    return db_shift


@router.get("", response_model=list[ShiftRead])
def list_shifts(
    worker_id: int | None = None,
    start_after: datetime | None = None,
    end_before: datetime | None = None,
    sort_by: Literal["start_time", "end_time", "created_at"] | None = None,
    order: Literal["asc", "desc"] = "asc",
    session: Session = Depends(get_session),
):
    """List shifts, optionally filtered by worker and/or a date range.

    `start_after` / `end_before` filter on the shift's own start_time, e.g.
    ?start_after=2026-08-10T00:00:00&end_before=2026-08-17T00:00:00 returns
    shifts starting in that window.
    """
    statement = select(Shift)
    if worker_id is not None:
        statement = statement.where(Shift.worker_id == worker_id)
    if start_after is not None:
        statement = statement.where(Shift.start_time >= start_after)
    if end_before is not None:
        statement = statement.where(Shift.start_time <= end_before)
    sort_column = {
        "start_time": Shift.start_time,
        "end_time": Shift.end_time,
        "created_at": Shift.created_at,
    }[sort_by or "start_time"]
    statement = statement.order_by(
        asc(sort_column) if order == "asc" else desc(sort_column)
    )

    return session.exec(statement).all()

@router.get("/upcoming", response_model=list[ShiftRead])
def list_upcoming_shifts(
    minutes: int=DEFAULT_LOOKAHEAD_MINUTES,
    session: Session=Depends(get_session)
):
    """Shifts starting within the next `minutes` (defaults to the background
    job's lookahead window)."""
    return get_upcoming_shifts(session, minutes)


@router.get("/{shift_id}", response_model=ShiftRead)
def get_shift(shift_id: int, session: Session = Depends(get_session)):
    """
    GET request: 
    ---
    Get a shift record, `{parameter}` required is the shift record ID. 
    ---
    Returns:
    - `worker_id`
    - `start_time`
    - `end_time`
    - `id` -> this is the shift record ID.
    """
    shift = session.get(Shift, shift_id)
    if shift is None:
        raise HTTPException(status_code=404, detail="Shift not found")
    return shift


@router.delete("/{shift_id}", status_code=204)
def delete_shift(shift_id: int, session: Session = Depends(get_session)):
    """
    DELETE request:
    ---
    Delete a shift record. 
    ---
    Required parameter is the shift record `id` 
    ---
    If there is no matching ID a "Shift not found" error is thrown. 
    """
    shift = session.get(Shift, shift_id)
    if shift is None:
        raise HTTPException(status_code=404, detail="Shift not found")
    session.delete(shift)
    session.commit()

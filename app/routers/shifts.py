
from datetime import datetime, timedelta, UTC
from typing import Literal, Annotated


from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import asc, desc
from sqlmodel import Session, select

from app.background import DEFAULT_LOOKAHEAD_MINUTES, get_upcoming_shifts
from app.conflicts import find_conflicting_shifts
from app.database import get_session
from app.models import (
    FilterParams,
    BulkShiftResponse,
    RejectedShift,
    Shift,
    ShiftConflictGroup,
    ShiftCreate,
    ShiftRead,
    Worker,
    RejectedShift,
    BulkShiftResponse,
    ShiftUpdate
)
from app.rate_limiter import limiter

router = APIRouter(prefix="/shifts", tags=["shifts"])


@router.post("", response_model=ShiftRead, status_code=201)
@limiter.limit("10/30seconds")
def create_shift(
    request: Request,
    shift: ShiftCreate,
    session: Session = Depends(get_session),
):
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
    if not worker.active:
        raise HTTPException(
            status_code=400,
            detail="Cannot schedule a shift for an inactive worker",
        )

    conflicts = find_conflicting_shifts(session, shift.worker_id, shift.start_time, shift.end_time)
    if conflicts:
        conflict_ids = ", ".join(str(c.id) for c in conflicts)
        raise HTTPException(
            status_code=409,
            detail=(f"Shift conflicts with existing shift(s) for this worker: {conflict_ids}"),
        )

    db_shift = Shift.model_validate(shift)
    session.add(db_shift)
    session.commit()
    session.refresh(db_shift)
    return db_shift


@router.put("/{shift_id}", response_model=ShiftRead)
def update_shift(
    shift_id: int,
    shift_data: ShiftUpdate,
    session: Session = Depends(get_session)
):
    """
    PUT request:
    Update an existing shift record by its ID.
    -----------
    - **shift_id**: integer ID of the shift to update
    - **worker_id**: integer ID of the worker assigned
    - **start_time**: datetime string (ISO format)
    - **end_time**: datetime string (ISO format)
    -----------
    Returns the updated shift object.
    Throws:
    - 404 if shift_id is not found
    - 404 if worker_id is not found
    - 409 if shift conflicts with an existing shift for the worker
    """
    # 1. Fetch existing shift record
    db_shift = session.get(Shift, shift_id)
    if db_shift is None:
        raise HTTPException(status_code=404, detail="Shift not found")

    # 2. Verify worker exists and is active
    worker = session.get(Worker, shift_data.worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")
    if not worker.active:
        raise HTTPException(
            status_code=400,
            detail="Cannot schedule a shift for an inactive worker",
        )

    # 3. Check for shift conflicts (excluding the shift currently being updated!)
    conflicts = find_conflicting_shifts(
        session,
        shift_data.worker_id,
        shift_data.start_time,
        shift_data.end_time,
        exclude_shift_id=shift_id,
    )
    if conflicts:
        conflict_ids = ", ".join(str(c.id) for c in conflicts)
        raise HTTPException(
            status_code=409,
            detail=f"Shift conflicts with existing shift(s) for this worker: {conflict_ids}",
        )

    # 4. Update attributes
    db_shift.worker_id = shift_data.worker_id
    db_shift.start_time = shift_data.start_time
    db_shift.end_time = shift_data.end_time
    db_shift.notes = shift_data.notes

    session.add(db_shift)
    session.commit()
    session.refresh(db_shift)
    return db_shift
@router.post("/bulk", response_model=BulkShiftResponse, status_code=201)
@limiter.limit("10/30seconds")
def create_shifts_bulk(
    request: Request,
    shifts: list[ShiftCreate], 
    session: Session = Depends(get_session)
):
    """
    POST request:
    ---
    Create multiple shifts for workers in bulk.
    ---
    Fields:
    - **Start time**
    - **End time**
    - **Worker ID**
    ---
    Maximum 10 shifts allowed per bulk request (throws 400 if exceeded).
    Rate limited to 10 requests per 30 seconds.
    ---
    If any worker ID does not exist, an error will be thrown.
    If any shift conflicts with existing shifts for the same worker, an error will be thrown.
    """
    
    if len(shifts) > 10:
        raise HTTPException(
            status_code=400,
            detail="Bulk shift creation limit exceeded. Maximum 10 shifts allowed per request.",
        )
    
    db_shifts = []
    rejected_shifts = []
    for shift in shifts:
        worker = session.get(Worker, shift.worker_id)
        if worker is None:
            rejected_shifts.append(RejectedShift(shift=shift, reason=f"Worker {shift.worker_id} not found"))
            continue
        elif worker.active is False:
            rejected_shifts.append(RejectedShift(shift=shift, reason=f"Worker {shift.worker_id} is not active"))
            continue

        conflicts = find_conflicting_shifts(session, shift.worker_id, shift.start_time, shift.end_time)
        if conflicts:
            conflict_ids = ", ".join(str(c.id) for c in conflicts)
            rejected_shifts.append(
                RejectedShift(
                    shift=shift,
                    reason=f"Shift conflicts with existing shift(s) for this worker: {conflict_ids}",
                )
            )
            continue

        db_shift = Shift.model_validate(shift)
        session.add(db_shift)
        session.flush()  # Ensure the shift gets an ID before committing
        db_shifts.append(db_shift)

    session.commit()
    for db_shift in db_shifts:
        session.refresh(db_shift)
    return BulkShiftResponse(
        accepted_shifts=[ShiftRead.model_validate(s) for s in db_shifts], rejected_shifts=rejected_shifts
    )


@router.get("", response_model=list[ShiftRead])
def list_shifts(
    filters: Annotated[FilterParams, Depends()],
    session: Session = (Depends(get_session)),
):
    """List shifts, optionally filtered by worker and/or a date range.

    `start_after` / `end_before` filter on the shift's own start_time, e.g.
    ?start_after=2026-08-10T00:00:00&end_before=2026-08-17T00:00:00 returns
    shifts starting in that window.
    """
    statement = select(Shift)
    if filters.worker_id is not None:
        statement = statement.where(Shift.worker_id == filters.worker_id)
    if filters.start_after is not None:
        statement = statement.where(Shift.start_time >= filters.start_after)
    if filters.end_before is not None:
        statement = statement.where(Shift.start_time <= filters.end_before)
    sort_column = {
        "start_time": Shift.start_time,
        "end_time": Shift.end_time,
        "created_at": Shift.created_at,
    }[filters.sort_by or "start_time"]
    statement = statement.order_by(asc(sort_column) if filters.order == "asc" else desc(sort_column))
    statement = statement.offset(filters.offset).limit(filters.limit)
    return session.exec(statement).all()


@router.get("/upcoming", response_model=list[ShiftRead])
def list_upcoming_shifts(
    minutes: int = DEFAULT_LOOKAHEAD_MINUTES, worker_id: int | None = None, session: Session = Depends(get_session)
):
    """Shifts starting within the next `minutes` (defaults to the background
    job's lookahead window)."""
    return get_upcoming_shifts(session=session, worker_id=worker_id, lookahead_minutes=minutes)

@router.get("/today", response_model=list[ShiftRead])
def list_today_shifts(
    worker_id: int | None = None,
    session: Session = Depends(get_session)
):
    """Shifts starting within the current UTC calendar day.
    Filters on start_time only, consistent with how /shifts and /shifts/upcoming
    already filter. A shift that started yesterday and runs past midnight into
    today is not included since its start_time falls on the previous day
    """
    today=datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow=today+timedelta(days=1)
    
    statement=select(Shift).where(tomorrow>Shift.start_time)
    statement=statement.where(Shift.start_time>=today)
    if worker_id is not None:
        statement = statement.where(Shift.worker_id == worker_id)

    all_shifts = session.exec(statement).all()

    return all_shifts

@router.get("/conflicts", response_model=list[ShiftConflictGroup])
def list_conflicts(session: Session = Depends(get_session)):
    """List all workers with conflicting shifts, along with the conflicting shifts.

    This endpoint is useful for identifying scheduling issues.
    """
    statement = select(Shift).order_by(Shift.worker_id, Shift.start_time)
    all_shifts = session.exec(statement).all()

    shifts_by_worker: dict[int, list[Shift]] = {}
    for shift in all_shifts:
        shifts_by_worker.setdefault(shift.worker_id, []).append(shift)

    conflict_groups = []
    for worker_id, shifts in shifts_by_worker.items():
        conflicting = set()
        for shift in shifts:
            conflicts = find_conflicting_shifts(
                session,
                worker_id,
                shift.start_time,
                shift.end_time,
                exclude_shift_id=shift.id,
            )
            if conflicts:
                conflicting.add(shift.id)
                conflicting.update(c.id for c in conflicts)

        if conflicting:
            conflicting_shifts = [s for s in shifts if s.id in conflicting]
            conflict_groups.append(
                ShiftConflictGroup(
                    worker_id=worker_id,
                    conflicting_shifts=[ShiftRead.model_validate(s) for s in conflicting_shifts],
                )
            )
    return conflict_groups


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
@limiter.limit("10/30seconds")
def delete_shift(request: Request, shift_id: int, session: Session = Depends(get_session)):
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

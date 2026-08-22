"""Shift management routes for creating, querying, bulk importing, and deleting shifts.
Authentication Policy:
- Mutating endpoints (POST, DELETE) require a valid JWT Bearer token via `require_auth`.
- Read-only endpoints (GET) are publicly accessible without authentication to allow
  team-wide visibility into schedules, upcoming shifts, today's roster, and conflicts.
"""

from datetime import datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import asc, desc
from sqlmodel import Session, select

from app.auth import require_auth
from app.background import DEFAULT_LOOKAHEAD_MINUTES, get_upcoming_shifts
from app.conflicts import find_conflicting_shifts
from app.database import get_session
from app.models import (
    BulkShiftResponse,
    RejectedShift,
    Shift,
    ShiftConflictGroup,
    ShiftCreate,
    ShiftRead,
    ShiftUpdate,
    Worker,
)
from app.rate_limiter import limiter

router = APIRouter(prefix="/shifts", tags=["shifts"])


@router.post("", response_model=ShiftRead, status_code=201)
@limiter.limit("10/30seconds")
def create_shift(
    request: Request,
    shift: ShiftCreate,
    session: Session = Depends(get_session),
    current_worker: Worker = Depends(require_auth),
):
    """
    POST request:
    Create a new shift for a worker.
    -----------
    - **worker_id**: integer ID of the assigned worker (required)
    - **start_time**: ISO-8601 start timestamp (required)
    - **end_time**: ISO-8601 end timestamp (required)
    - **notes**: Optional notes string (up to 300 characters)
    -----------
    Requirements & Validations:
    - Requires Bearer authentication (`require_auth`).
    - Rate limited to 10 requests per 30 seconds.
    - Worker must exist (throws 404 if not found).
    - Worker must be active (throws 400 if `active` is False).
    - Shift must not conflict/overlap with existing shifts for the same worker (throws 409).
    - Shift duration must be between 30 minutes and 24 hours (throws 422).
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
            detail=f"Shift conflicts with existing shift(s) for this worker: {conflict_ids}",
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
    session: Session = Depends(get_session),
    current_worker: Worker = Depends(require_auth)
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
def create_shifts_bulk(
    shifts: list[ShiftCreate],
    session: Session = Depends(get_session),
    current_worker: Worker = Depends(require_auth),
):
    """
    POST request:
    Create multiple shifts for workers in bulk.
    -----------
    - Accepts a JSON list of shift creation objects.
    -----------
    Requirements & Validations:
    - Requires Bearer authentication (`require_auth`).
    - Evaluates each shift independently:
      * Valid shifts are committed and returned in `accepted_shifts`.
      * Shifts failing validation (worker not found, inactive worker, DB conflict,
        or intra-batch conflict) are skipped and itemized in `rejected_shifts` with the reason.
    """
    db_shifts: list[Shift] = []
    rejected_shifts: list[RejectedShift] = []

    for shift in shifts:
        worker = session.get(Worker, shift.worker_id)
        if worker is None:
            rejected_shifts.append(
                RejectedShift(shift=shift, reason=f"Worker {shift.worker_id} not found")
            )
            continue
        elif worker.active is False:
            rejected_shifts.append(
                RejectedShift(shift=shift, reason=f"Worker {shift.worker_id} is not active")
            )
            continue

        # Check against persisted DB shifts
        conflicts = find_conflicting_shifts(
            session, shift.worker_id, shift.start_time, shift.end_time
        )
# Check against shifts accepted earlier in this exact bulk batch
        intra_batch_conflict = any(
            accepted.worker_id == shift.worker_id
            and max(accepted.start_time, shift.start_time) < min(accepted.end_time, shift.end_time)
            for accepted in db_shifts
        )

        if conflicts or intra_batch_conflict:
            conflict_ids = ", ".join(str(c.id) for c in conflicts) if conflicts else "intra-batch"
            rejected_shifts.append(
                RejectedShift(
                    shift=shift,
                    reason=f"Shift conflicts with existing shift(s) for this worker: {conflict_ids}",
                )
            )
            continue

        db_shift = Shift.model_validate(shift)
        session.add(db_shift)
        session.flush() # Ensure the shift gets an ID before committing
        db_shifts.append(db_shift)

    session.commit()
    for db_shift in db_shifts:
        session.refresh(db_shift)

    return BulkShiftResponse(
        accepted_shifts=[ShiftRead.model_validate(s) for s in db_shifts],
        rejected_shifts=rejected_shifts,
    )


@router.get("", response_model=list[ShiftRead])
def list_shifts(
    worker_id: Optional[int] = Query(
        default=None, description="Filter shifts by specific worker ID"
    ),
    start_after: Optional[datetime] = Query(
        default=None, description="Filter shifts starting on or after this ISO-8601 timestamp"
    ),
    end_before: Optional[datetime] = Query(
        default=None, description="Filter shifts starting on or before this ISO-8601 timestamp"
    ),
    sort_by: Literal["start_time", "end_time", "created_at"] = Query(
        default="start_time", description="Field to sort results by"
    ),
    order: Literal["asc", "desc"] = Query(
        default="asc", description="Sort order direction ('asc' or 'desc')"
    ),
    session: Session = Depends(get_session),
):
    """
    GET request:
    List shifts, optionally filtered by worker and/or a date range, with configurable sorting.
    -----------
    - `start_after` / `end_before` filter on the shift's own `start_time` (e.g.
      `?start_after=2026-08-10T00:00:00&end_before=2026-08-17T00:00:00` returns shifts
      starting in that window).
    - `sort_by`: `"start_time"`, `"end_time"`, or `"created_at"` (defaults to `"start_time"`).
    - `order`: `"asc"` or `"desc"` (defaults to `"asc"`).
    -----------
    Publicly accessible without authentication.
    """
    statement = select(Shift)
    if worker_id is not None:
        statement = statement.where(Shift.worker_id == worker_id)
    if start_after is not None:
        statement = statement.where(Shift.start_time >= start_after)
    if end_before is not None:
        statement = statement.where(Shift.start_time <= end_before)

    sort_column = getattr(Shift, sort_by)
    statement = statement.order_by(asc(sort_column) if order == "asc" else desc(sort_column))

    return session.exec(statement).all()


@router.get("/upcoming", response_model=list[ShiftRead])
def list_upcoming_shifts(
    minutes: int = Query(
        default=DEFAULT_LOOKAHEAD_MINUTES,
        description="Lookahead window in minutes from current UTC time",
    ),
    worker_id: Optional[int] = Query(
        default=None, description="Optional worker ID to filter upcoming shifts"
    ),
    session: Session = Depends(get_session),
):
    """
    GET request:
    Retrieve shifts starting within the next `minutes` window (defaults to the background job's
    lookahead window).
    -----------
    - **minutes**: Optional lookahead duration in minutes.
    - **worker_id**: Optional worker ID filter.
    -----------
    Publicly accessible without authentication.
    """
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
    today=datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow=today+timedelta(days=1)
    
    statement=select(Shift).where(tomorrow>Shift.start_time)
    statement=statement.where(Shift.start_time>=today)
    if worker_id is not None:
        statement = statement.where(Shift.worker_id == worker_id)

    all_shifts = session.exec(statement).all()

    return all_shifts

@router.get("/today", response_model=list[ShiftRead])
def list_today_shifts(
    worker_id: Optional[int] = Query(
        default=None, description="Optional worker ID to filter today's shifts"
    ),
    session: Session = Depends(get_session),
):
    """
    GET request:
    Retrieve shifts starting within the current UTC calendar day.
    -----------
    Filters on `start_time` only, consistent with how `/shifts` and `/shifts/upcoming`
    already filter. A shift that started yesterday and runs past midnight into today
    is not included since its `start_time` falls on the previous day.
    -----------
    Publicly accessible without authentication.
    """
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    statement = select(Shift).where(Shift.start_time >= today, Shift.start_time < tomorrow)
    if worker_id is not None:
        statement = statement.where(Shift.worker_id == worker_id)

    return session.exec(statement).all()


@router.get("/conflicts", response_model=list[ShiftConflictGroup])
def list_conflicts(session: Session = Depends(get_session)):
    """
    GET request:
    List all workers with conflicting shifts, along with their conflicting shift details.
    -----------
    This queries the database and groups overlapping shift schedules by worker ID to identify
    scheduling issues.
    -----------
    Publicly accessible without authentication.
    """
    statement = select(Shift).order_by(Shift.worker_id, Shift.start_time)
    all_shifts = session.exec(statement).all()

    shifts_by_worker: dict[int, list[Shift]] = {}
    for shift in all_shifts:
        shifts_by_worker.setdefault(shift.worker_id, []).append(shift)

    conflict_groups: list[ShiftConflictGroup] = []
    for worker_id, shifts in shifts_by_worker.items():
        conflicting_ids: set[int] = set()
        n = len(shifts)
        for i in range(n):
            for j in range(i + 1, n):
                s1, s2 = shifts[i], shifts[j]
                # Overlap condition: max(start1, start2) < min(end1, end2)
                if max(s1.start_time, s2.start_time) < min(s1.end_time, s2.end_time):
                    conflicting_ids.add(s1.id)
                    conflicting_ids.add(s2.id)

        if conflicting_ids:
            conflicting_shifts = [s for s in shifts if s.id in conflicting_ids]
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
    Get a single shift record by its database ID.
    -----------
    - **shift_id**: integer ID of the shift record.
    -----------
    Returns the complete shift record. Throws 404 if shift is not found.
    Publicly accessible without authentication.
    """
    shift = session.get(Shift, shift_id)
    if shift is None:
        raise HTTPException(status_code=404, detail="Shift not found")
    return shift


@router.delete("/{shift_id}", status_code=204)
@limiter.limit("10/30seconds")
def delete_shift(
    request: Request,
    shift_id: int,
    session: Session = Depends(get_session),
    current_worker: Worker = Depends(require_auth),
):
    """
    DELETE request:
    Delete an existing shift record by ID.
    -----------
    - **shift_id**: integer ID of the shift record to delete.
    -----------
    Requirements & Validations:
    - Requires Bearer authentication (`require_auth`).
    - Rate limited to 10 requests per 30 seconds.
    - Throws 404 if shift is not found.
    """
    shift = session.get(Shift, shift_id)
    if shift is None:
        raise HTTPException(status_code=404, detail="Shift not found")
    session.delete(shift)
    session.commit()


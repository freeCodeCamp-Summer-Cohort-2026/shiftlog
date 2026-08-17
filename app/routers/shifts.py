from datetime import datetime
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


@router.post("/bulk", response_model=BulkShiftResponse, status_code=201)
def create_shifts_bulk(
    shifts: list[ShiftCreate],
    session: Session = Depends(get_session),
    current_worker: Worker = Depends(require_auth),
):
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
        session.flush()
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
    worker_id: Optional[int] = None,
    start_after: Optional[datetime] = None,
    end_before: Optional[datetime] = None,
    sort_by: Literal["start_time", "end_time", "created_at"] = "start_time",
    order: Literal["asc", "desc"] = "asc",
    session: Session = Depends(get_session),
):
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
    minutes: int = DEFAULT_LOOKAHEAD_MINUTES,
    worker_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    """Shifts starting within the next `minutes` (defaults to the background
    job's lookahead window)."""
    return get_upcoming_shifts(session=session, worker_id=worker_id, lookahead_minutes=minutes)


@router.get("/conflicts", response_model=list[ShiftConflictGroup])
def list_conflicts(session: Session = Depends(get_session)):
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
    shift = session.get(Shift, shift_id)
    if shift is None:
        raise HTTPException(status_code=404, detail="Shift not found")
    session.delete(shift)
    session.commit()
    
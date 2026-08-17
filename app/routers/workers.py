from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session, select

from app.database import get_session
from app.models import Shift, Worker, WorkerCreate, WorkerRead, WorkerSummary, WorkerUpdate
from app.rate_limiter import limiter
from app.auth import require_auth

router = APIRouter(prefix="/workers", tags=["workers"])


@router.post("", response_model=WorkerRead, status_code=201)
@limiter.limit("10/30seconds")
def create_worker(
    request: Request,
    worker: WorkerCreate,
    session: Session = Depends(get_session),
    current_worker: Worker = Depends(require_auth)
):
    worker.name = " ".join(worker.name.split())
    db_worker = Worker.model_validate(worker)
    session.add(db_worker)
    session.commit()
    session.refresh(db_worker)
    return db_worker


@router.put("/{worker_id}", response_model=WorkerRead)
@limiter.limit("10/30seconds")
def update_worker(
    request: Request,
    worker_id: int,
    worker: WorkerUpdate,
    session: Session = Depends(get_session),
    current_worker: Worker = Depends(require_auth)
):
    db_worker = session.get(Worker, worker_id)
    if db_worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")

    worker.name = " ".join(worker.name.split())
    db_worker.name = worker.name
    db_worker.role = worker.role
    
    session.add(db_worker)
    session.commit()
    session.refresh(db_worker)
    return db_worker


@router.get("", response_model=list[WorkerRead])
def list_workers(
    session: Session = Depends(get_session),
    role: Optional[str] = Query(
        default=None, description="Filter workers by their job role", examples=["Cashier", "Cook"]
    ),
):
    statement = select(Worker)
    if role is not None:
        statement = statement.where(Worker.role == role)
    return session.exec(statement).all()


@router.get("/{worker_id}", response_model=WorkerRead)
def get_worker(worker_id: int, session: Session = Depends(get_session)):
    worker = session.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")
    return worker


@router.delete("/{worker_id}", status_code=204)
def delete_worker(worker_id: int, session: Session = Depends(get_session),current_worker: Worker = Depends(require_auth)):
    worker = session.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Cascade delete shifts assigned to this worker
    shifts_statement = select(Shift).where(Shift.worker_id == worker_id)
    worker_shifts = session.exec(shifts_statement).all()
    for shift in worker_shifts:
        session.delete(shift)

    session.delete(worker)
    session.commit()


@router.get("/{worker_id}/summary", response_model=WorkerSummary)
def get_worker_hours_summary(
    worker_id: int,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    session: Session = Depends(get_session),
):
    worker = session.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")

    statement = select(Shift).where(Shift.worker_id == worker_id)
    if start is not None:
        statement = statement.where(Shift.start_time >= start)
    if end is not None:
        statement = statement.where(Shift.start_time <= end)

    shifts = session.exec(statement).all()
    total_hours = sum((shift.end_time - shift.start_time).total_seconds() / 3600 for shift in shifts)

    return WorkerSummary(worker_id=worker_id, total_hours=total_hours, shift_count=len(shifts))


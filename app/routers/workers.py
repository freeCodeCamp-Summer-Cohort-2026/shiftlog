from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Worker, WorkerCreate, WorkerRead
from app.routers import shifts

router = APIRouter(prefix="/workers", tags=["workers"])

@router.post("", response_model=WorkerRead, status_code=201)
def create_worker(worker: WorkerCreate, session: Session = Depends(get_session)):
    db_worker = Worker.model_validate(worker)
    session.add(db_worker)
    session.commit()
    session.refresh(db_worker)
    return db_worker


@router.get("", response_model=list[WorkerRead])
def list_workers(session: Session = Depends(get_session)):
    return session.exec(select(Worker)).all()


@router.get("/{worker_id}", response_model=WorkerRead)
def get_worker(worker_id: int, session: Session = Depends(get_session)):
    worker = session.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")
    return worker

@router.delete("/{worker_id}", status_code=204)
def delete_worker(worker_id: int, session: Session = Depends(get_session)):
    worker = session.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    @shifts.router.delete(
    session.delete(worker)
    session.commit()

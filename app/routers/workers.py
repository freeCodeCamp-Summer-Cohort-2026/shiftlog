from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Worker, WorkerCreate, WorkerRead

router = APIRouter(prefix="/workers", tags=["workers"])


@router.post("", response_model=WorkerRead, status_code=201)
def create_worker(worker: WorkerCreate, session: Session = Depends(get_session)):
    """
    POST request: 
    Create a worker with the following information:
    **name**: a string
    **role**: a string
    ----------
    An ID will be auto-assigned as a key in the database with the column name "id".
    """
    worker.name = " ".join(worker.name.split())
    db_worker = Worker.model_validate(worker)
    session.add(db_worker)
    session.commit()
    session.refresh(db_worker)
    return db_worker


@router.get("", response_model=list[WorkerRead])
def list_workers(session: Session = Depends(get_session)):
    """
    GET request:
    Get all workers in the database. 
    ----------
    This queries the database for all workers.
    """
    return session.exec(select(Worker)).all()


@router.get("/{worker_id}", response_model=WorkerRead)
def get_worker(worker_id: int, session: Session = Depends(get_session)):
    """
    GET request:
    Get a single worker based on their ID.
    -----------
    This queries the database for a specific worker ID, the parameter required is the database ID for a single worker. 
    -----------
    Returns name, role and id that was used to query (the parameter)
    `/workers/1` gets the worker with the ID of `1` 
    """
    worker = session.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")
    return worker

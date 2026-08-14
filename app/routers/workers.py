from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.database import get_session
from app.models import Worker, WorkerCreate, WorkerRead, WorkerUpdate
from app.rate_limiter import limiter

from typing import Optional

router = APIRouter(prefix="/workers", tags=["workers"])


@router.post("", response_model=WorkerRead, status_code=201)
@limiter.limit("10/30seconds")
def create_worker(
    request: Request,
    worker: WorkerCreate,
    session: Session = Depends(get_session),
):
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


@router.put("/{worker_id}", response_model=WorkerRead)
@limiter.limit("10/30seconds")
def update_worker(
    request: Request,
    worker_id: int,
    worker: WorkerUpdate,
    session: Session = Depends(get_session),
):
    """
    PUT request:
    Update an existing worker's details by their ID.
    -----------
    - **worker_id**: integer database ID
    - **name**: string
    - **role**: string
    -----------
    Returns the updated worker object.
    Throws a 404 error if worker is not found.
    """
    db_worker = session.get(Worker, worker_id)
    if db_worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Sanitize spaces in name (same as create_worker)
    worker.name = " ".join(worker.name.split())

    # Update worker attributes
    db_worker.name = worker.name
    db_worker.role = worker.role
    session.add(db_worker)
    session.commit()
    session.refresh(db_worker)

    return db_worker


@router.get("", response_model=list[WorkerRead])
def list_workers(session: Session = Depends(get_session), role: Optional[str] = Query(
        default=None,
        description="Filter workers by their job role",
        examples=["Cashier", "Cook"]
    )):
    """
    GET request:
    Get all workers in the database with optional role filtering.
    ----------
    This queries the database for all workers with optional role filtering.
    """
    statement = select(Worker)

    if role is not None:
        statement = statement.where(Worker.role == role)
    
    return session.exec(statement).all()


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

import jwt
from passlib.context import CryptContext

import os
from datetime import datetime,timedelta,timezone
from app.models import Worker, WorkerRead, RegisterRequest,LoginRequest

from fastapi import APIRouter, Depends, HTTPException,status
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from sqlmodel import Session, select
from app.database import get_session

security = HTTPBearer()

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(
    schemes=["bcrypt"],
)

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DATE = 7

def hash_password(password:str) -> str:
    return pwd_context.hash(password)

def verify_password(password:str,password_hash:str) -> bool:
    return pwd_context.verify(password,password_hash)

def create_access_token(worker_id: int) -> str:
    secret = os.getenv("JWT_SECRET")

    if not secret:
        raise RuntimeError("JWT_SECRET is not configured")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=JWT_EXPIRATION_DATE)

    payload = {
        "sub": str(worker_id),
        "iat": now,
        "exp": expires_at
    }

    return jwt.encode(payload,secret,algorithm=JWT_ALGORITHM)

    
@router.post("/register",status_code=201)
def register(data:RegisterRequest,session:Session = Depends(get_session)):
    existing_worker = session.exec(select(Worker).where(Worker.username == data.username)).first()
    if(existing_worker):
        raise HTTPException(status_code=409,detail="Username already exists")

    password_hash = hash_password(data.password)

    worker = Worker(
        username=data.username,
        password_hash=password_hash,
        name=data.name
    )

    session.add(worker)
    session.commit()
    session.refresh(worker)

    token = create_access_token(worker_id=worker.id)

    return {
        "token": token,
        "worker": WorkerRead.model_validate(worker)
    }

@router.post("/login")
def login(data: LoginRequest,session: Session = Depends(get_session)):
    worker = session.exec(select(Worker).where(Worker.username == data.username)).first()
    if worker is None:
        raise HTTPException(
            status_code=401,
            detail="Username doesn't exist"
        )

    if not verify_password(data.password,worker.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    token = create_access_token(
        worker_id=worker.id
    )

    return {
        "token": token,
        "worker": WorkerRead.model_validate(worker)
    }
    

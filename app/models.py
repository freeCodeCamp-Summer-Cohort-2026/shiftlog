"""SQLModel table definitions plus their create/read request-response shapes.

SQLModel lets a single class double as a Pydantic schema and a SQLAlchemy
table, so the *Base classes here define shared fields, the table=True classes
are the DB models, and the *Create/*Read classes are what the API actually
accepts and returns.
"""

from datetime import datetime
from typing import Optional

from pydantic import field_validator
from sqlmodel import Field, SQLModel


class WorkerBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=50)


class Worker(WorkerBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class WorkerCreate(WorkerBase):
    pass


class WorkerRead(WorkerBase):
    id: int


class ShiftBase(SQLModel):
    worker_id: int = Field(foreign_key="worker.id", index=True)
    start_time: datetime
    end_time: datetime

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, end_time: datetime, info):
        start_time = info.data.get("start_time")
        if start_time is not None and end_time <= start_time:
            raise ValueError(f"end_time ({end_time.isoformat()}) must be after start_time ({start_time.isoformat()})")
        return end_time


class Shift(ShiftBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ShiftCreate(ShiftBase):
    pass


class ShiftRead(ShiftBase):
    id: int
    created_at: datetime

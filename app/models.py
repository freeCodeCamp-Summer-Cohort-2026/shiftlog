"""SQLModel table definitions plus their create/read request-response shapes.

SQLModel lets a single class double as a Pydantic schema and a SQLAlchemy
table, so the *Base classes here define shared fields, the table=True classes
are the DB models, and the *Create/*Read classes are what the API actually
accepts and returns.
"""

import datetime
from typing import Optional

from pydantic import computed_field, field_validator
from sqlmodel import Field, SQLModel


class WorkerBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=50)
    active: bool = Field(default=True, description="Indicates whether the worker is active or not")
    pay: Optional[float] = Field(default=None, description="Hourly pay of the worker")

    @field_validator("name")
    @classmethod
    def name_length(cls, name):
        name=" ".join(name.split())
        if (len(name) == 0):
            raise ValueError('Name cannot be empty after removing whitespaces.')
        return name

    @field_validator("pay")
    @classmethod
    def pay_is_positive(cls, pay: float, info):
        if pay is not None and pay < 0:
            raise ValueError("Pay cannot be a negative value.")
        return pay
    
class Worker(WorkerBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class WorkerCreate(WorkerBase):
    pass


class WorkerUpdate(WorkerBase):
    pass


class WorkerRead(WorkerBase):
    id: int


class ShiftBase(SQLModel):
    worker_id: int = Field(foreign_key="worker.id", index=True)
    start_time: datetime.datetime = Field(index=True)
    end_time: datetime.datetime
    notes: Optional[str] = Field(default=None, max_length=300)

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, end_time: datetime.datetime, info):
        start_time = info.data.get("start_time")
        if start_time is not None and end_time <= start_time:
            raise ValueError(f"end_time ({end_time.isoformat()}) must be after start_time ({start_time.isoformat()})")
        return end_time

    @field_validator("end_time")
    @classmethod
    def end_start_delta(cls, end_time:datetime.datetime, info):
        start_time = info.data.get("start_time")
        if start_time is not None and (((end_time - start_time) > datetime.timedelta(hours=24))or
                                       ((end_time - start_time) < datetime.timedelta(minutes=30))):
            raise ValueError("A shift must last at least 30 minutes and no more than 24 hours.")
        return end_time

class Shift(ShiftBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # added lambda here when updating to datetime.now(datetime.UTC) to avoid deprecation warnings about datetime.datetime.utcnow(). Using lambda to avoid calling the function right away.
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC))


class ShiftCreate(ShiftBase):
    period: Optional[str]  = Field(default=None, max_length=20)
    duration: Optional[str] = Field(default=None, max_length=20)
    repeat: Optional[int] = Field(default=None)
    end_date: Optional[datetime.datetime] = Field(default=None)


class ShiftRead(ShiftBase):
    id: int
    created_at: datetime.datetime

    @computed_field
    @property
    def duration_hours(self) -> float:
        shift_duration = (self.end_time - self.start_time).total_seconds() / 3600
        return shift_duration


class ShiftConflictGroup(SQLModel):
    worker_id: int
    conflicting_shifts: list[ShiftRead]


class ShiftUpdate(ShiftBase):
    pass
class WorkerSummary(SQLModel):
    worker_id: int
    total_hours: float
    shift_count: int
    average_shift_hours: float


class OrgHoursSummary(SQLModel):
    workers: list[WorkerSummary]
    grand_total_hours: float
    total_shift_count: int


class RejectedShift(SQLModel):
    shift: ShiftCreate
    reason: str


class BulkShiftResponse(SQLModel):
    accepted_shifts: list[ShiftRead]
    rejected_shifts: list[RejectedShift]

class DeleteBulkShiftResponse(SQLModel):
    deleted_ids: list[int]
    not_found_ids: list[int]

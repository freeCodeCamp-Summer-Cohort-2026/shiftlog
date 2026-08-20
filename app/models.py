"""SQLModel table definitions plus their create/read request-response shapes.

SQLModel lets a single class double as a Pydantic schema and a SQLAlchemy
table, so the *Base classes here define shared fields, the table=True classes
are the DB models, and the *Create/*Read classes are what the API actually
accepts and returns.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import computed_field, field_validator
from sqlalchemy import DateTime, TypeDecorator
from sqlmodel import Field, SQLModel


class UtcDateTime(TypeDecorator):
    """A DateTime type that guarantees datetimes are timezone-aware UTC objects."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc)
        return value


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkerBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=50)
    active: bool = Field(default=True, description="Indicates whether the worker is active or not")
    pay: Optional[float] = Field(default=None, description="Hourly pay of the worker")

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
    start_time: datetime = Field(index=True, sa_type=UtcDateTime)
    end_time: datetime = Field(sa_type=UtcDateTime)
    notes: Optional[str] = Field(default=None, max_length=300)

    @field_validator("start_time", "end_time", mode="after")
    @classmethod
    def ensure_utc(cls, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, end_time: datetime, info):
        start_time = info.data.get("start_time")
        if start_time is not None and end_time <= start_time:
            raise ValueError(
                f"end_time ({end_time.isoformat()}) must be after start_time ({start_time.isoformat()})"
            )
        return end_time

    @field_validator("end_time")
    @classmethod
    def end_start_delta(cls, end_time: datetime, info):
        start_time = info.data.get("start_time")
        if start_time is not None and (
            ((end_time - start_time) > timedelta(hours=24))
            or ((end_time - start_time) < timedelta(minutes=30))
        ):
            raise ValueError("A shift must last at least 30 minutes and no more than 24 hours.")
        return end_time


class Shift(ShiftBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UtcDateTime)


class ShiftCreate(ShiftBase):
    pass


class ShiftRead(ShiftBase):
    id: int
    created_at: datetime

    @computed_field
    @property
    def duration_hours(self) -> float:
        shift_duration = (self.end_time - self.start_time).total_seconds() / 3600
        return shift_duration


class ShiftConflictGroup(SQLModel):
    worker_id: int
    conflicting_shifts: list[ShiftRead]


class WorkerSummary(SQLModel):
    worker_id: int
    total_hours: float
    shift_count: int


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

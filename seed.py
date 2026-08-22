"""Populate the database with a handful of workers and shifts.

Usage:
    python seed.py

Safe to run against a fresh database (tables are created if missing). Not
safe to run twice against the same database without clearing it first - it
will attempt to insert duplicate workers and may hit shift conflicts.
"""

from datetime import datetime, timedelta, UTC

from sqlmodel import Session

from app.database import create_db_and_tables, engine
from app.models import Shift, Worker

WORKERS = [
    {"name": "Alice Rivera", "role": "Barista", "pay":10.0},
    {"name": "Bilal Osei", "role": "Cashier", "pay":12.5},
    {"name": "Carmen Diaz", "role": "Shift Lead", "pay":30},
    {"name": "Dev Patel", "role": "Cook", "pay":25.0},
    {"name": "Elin Sorensen", "role": "Cashier"},
]


def seed() -> None:
    create_db_and_tables()

    with Session(engine) as session:
        workers = [Worker(**data) for data in WORKERS]
        session.add_all(workers)
        session.commit()
        for worker in workers:
            session.refresh(worker)

        alice, bilal, carmen, dev, elin = workers

        # Anchor shifts to "today" at fixed hours so seeded data is always
        # relevant regardless of when you run the script.
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

        shifts = [
            Shift(
                worker_id=alice.id,
                start_time=today + timedelta(hours=7),
                end_time=today + timedelta(hours=15),
            ),
            Shift(
                worker_id=bilal.id,
                start_time=today + timedelta(hours=9),
                end_time=today + timedelta(hours=17),
            ),
            Shift(
                worker_id=carmen.id,
                start_time=today + timedelta(hours=8),
                end_time=today + timedelta(hours=16),
            ),
            Shift(
                worker_id=dev.id,
                start_time=today + timedelta(hours=6),
                end_time=today + timedelta(hours=14),
            ),
            Shift(
                worker_id=elin.id,
                start_time=today + timedelta(hours=15),
                end_time=today + timedelta(hours=23),
            ),
            # Tomorrow, so filtering by date range has something to exclude.
            Shift(
                worker_id=alice.id,
                start_time=today + timedelta(days=1, hours=7),
                end_time=today + timedelta(days=1, hours=15),
            ),
        ]
        session.add_all(shifts)
        session.commit()

    print(f"Seeded {len(WORKERS)} workers and {len(shifts)} shifts.")


if __name__ == "__main__":
    seed()

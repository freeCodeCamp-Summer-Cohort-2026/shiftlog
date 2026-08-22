from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, create_engine, inspect, text
from sqlmodel import Session, select
from sqlmodel.pool import StaticPool

from app.database import apply_schema_migrations
from app.models import Shift


def test_migration_adds_archived_to_legacy_shift_table():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata = MetaData()
    Table(
        "shift",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("worker_id", Integer, nullable=False),
        Column("start_time", DateTime, nullable=False),
        Column("end_time", DateTime, nullable=False),
        Column("notes", String(300), nullable=True),
        Column("created_at", DateTime, nullable=False),
    )
    metadata.create_all(test_engine)

    # Insert a record into legacy table (which has no archived column)
    with test_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO shift (worker_id, start_time, end_time, created_at) "
                "VALUES (1, '2026-08-20 09:00:00', '2026-08-20 17:00:00', '2026-08-20 08:00:00')"
            )
        )

    # Verify column does not exist yet
    inspector = inspect(test_engine)
    columns_before = {c["name"] for c in inspector.get_columns("shift")}
    assert "archived" not in columns_before

    # Apply migration
    apply_schema_migrations(test_engine)

    # Verify column now exists
    inspector = inspect(test_engine)
    columns_after = {c["name"] for c in inspector.get_columns("shift")}
    assert "archived" in columns_after

    # Verify existing record can be queried with SQMModel and has archived=False
    with Session(test_engine) as session:
        shift = session.exec(select(Shift)).first()
        assert shift is not None
        assert shift.archived is False

    # Verify idempotency: running migration again does not error
    apply_schema_migrations(test_engine)

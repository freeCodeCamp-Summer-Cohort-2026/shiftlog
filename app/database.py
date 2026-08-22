"""Database engine and session setup.

Keep this deliberately simple for a sprint exercise: SQLModel handles table
creation on startup (see app.main) instead of using Alembic migrations.
"""

import os

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://shiftlog:shiftlog_dev_password@localhost:5432/shiftlog",
)

# `echo=False` keeps app logs readable; flip to True locally if you need to
# see the generated SQL while debugging.
engine = create_engine(DATABASE_URL, echo=False)


def apply_schema_migrations(target_engine=None) -> None:
    """Apply lightweight schema migrations for newly added model fields on existing tables."""
    active_engine = target_engine or engine
    inspector = inspect(active_engine)
    if inspector.has_table("shift"):
        columns = {col["name"] for col in inspector.get_columns("shift")}
        if "archived" not in columns:
            with active_engine.begin() as conn:
                if active_engine.dialect.name == "postgresql":
                    conn.execute(
                        text("ALTER TABLE shift ADD COLUMN archived BOOLEAN NOT NULL DEFAULT FALSE")
                    )
                else:
                    conn.execute(
                        text("ALTER TABLE shift ADD COLUMN archived BOOLEAN NOT NULL DEFAULT 0")
                    )


def create_db_and_tables() -> None:
    """Create all tables that don't already exist and ensure schema migrations are applied."""
    SQLModel.metadata.create_all(engine)
    apply_schema_migrations(engine)


def get_session():
    """FastAPI dependency that yields a database session per request."""
    with Session(engine) as session:
        yield session

"""Database engine and session setup.

Keep this deliberately simple for a sprint exercise: SQLModel handles table
creation on startup (see app.main) instead of using Alembic migrations.
"""

import os
from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine


# Load variables from .env into os.environ
load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URLpostgresql://shiftlog:shiftlog_dev_password@localhost:5432/shiftlog",
)

# `echo=False` keeps app logs readable; flip to True locally if you need to
# see the generated SQL while debugging.
engine = create_engine(DATABASE_URL, echo=False)


def create_db_and_tables() -> None:
    """Create all tables that don't already exist. Called on app startup."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency that yields a database session per request."""
    with Session(engine) as session:
        yield session

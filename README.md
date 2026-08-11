# ShiftLog

A small scheduling/time-tracking API. Workers get scheduled onto shifts;
ShiftLog rejects shifts that overlap for the same worker, lets you filter
shifts by worker or date range, and runs a lightweight background job that
logs shifts starting soon.

Built as the starter repo for the freeCodeCamp/NHCarrigan Summer 2026
Cohort sprint phase. It's a real, runnable app - fork/branch it, pick up an
issue, and open a PR.

## Stack

- [FastAPI](https://fastapi.tiangolo.com/) for the HTTP API
- [SQLModel](https://sqlmodel.tiangolo.com/) (SQLAlchemy + Pydantic) for models and validation
- PostgreSQL for storage
- `docker-compose` to run everything with one command
- `pytest` + FastAPI's `TestClient` for tests

## Quickstart

```bash
cp .env.example .env
docker-compose up --build
```

The API will be available at `http://localhost:8000`. Interactive docs
(Swagger UI) are at `http://localhost:8000/docs`.

Tables are created automatically on startup - there's no migration step to
run. To load some sample workers and shifts once the stack is up:

```bash
docker-compose exec api python seed.py
```

### Running locally without Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Point DATABASE_URL at a Postgres instance you have running, e.g. one
# started with `docker-compose up db`.
export DATABASE_URL=postgresql://shiftlog:shiftlog_dev_password@localhost:5432/shiftlog

uvicorn app.main:app --reload
```

### Running tests

Tests run against an in-memory SQLite database, so no Postgres instance or
`.env` file is needed:

```bash
pip install -r requirements.txt
pytest
```

## API overview

### Workers

| Method | Path            | Description                |
|--------|-----------------|----------------------------|
| POST   | `/workers`      | Create a worker            |
| GET    | `/workers`      | List all workers           |
| GET    | `/workers/{id}` | Get a single worker        |

### Shifts

| Method | Path            | Description                                          |
|--------|-----------------|-------------------------------------------------------|
| POST   | `/shifts`       | Create a shift (rejects overlapping shifts, 409)      |
| GET    | `/shifts`       | List shifts, optionally filtered by `worker_id`, `start_after`, `end_before` |
| GET    | `/shifts/{id}`  | Get a single shift                                    |
| DELETE | `/shifts/{id}`  | Delete a shift                                        |

A shift conflicts with another shift for the same worker when their time ranges overlap. Back-to-back shifts (one ending exactly when the next starts) are not conflicts.

### How conflict detection works

ShiftLog checks for overlap with a standard half-open interval test:

    existing.start_time < new.end_time AND existing.end_time > new.start_time

If both conditions are true, the shifts overlap and the new shift is rejected with a 409.

**Example — conflict:**
- Existing shift: 9:00 AM – 5:00 PM
- New shift: 3:00 PM – 11:00 PM

`9:00 < 11:00` ✅ and `5:00 > 3:00` ✅ → both true, so this **conflicts**.

**Example — back-to-back, not a conflict:**
- Existing shift: 9:00 AM – 5:00 PM
- New shift: 5:00 PM – 11:00 PM

`5:00 > 5:00` is **false**, so the check fails and the shift is **allowed**. One shift ending exactly when the next begins does not overlap.

### Background job

On startup, ShiftLog kicks off a simple `asyncio` loop (see
`app/background.py`) that periodically checks for shifts starting soon and
logs them. It's intentionally not a full task queue like Celery - just
enough to demonstrate scheduled background work.

## Contributing

Picking up an issue for the cohort? See [CONTRIBUTING.md](CONTRIBUTING.md)
for the issue-claiming flow and how to run tests locally.

## License

[MIT](LICENSE)

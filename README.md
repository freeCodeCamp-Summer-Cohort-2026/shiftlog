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

**Requires Python 3.12** (see `.python-version`). `psycopg2-binary==2.9.9`
only ships prebuilt wheels through Python 3.12 - on 3.13+ pip falls back to
building it from source, which fails unless you happen to have PostgreSQL's
dev headers installed. If `pip install -r requirements.txt` fails with a
"Getting requirements to build wheel" error, this is almost certainly why -
switch to 3.12 rather than trying to fix the build.

```bash
python3.12 -m venv .venv
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

### Running tests with Docker

You can run the tests against an actual instance of Shiftlog, be sure it is a development instance, because tests may cause data changes or loss:

```bash
docker exec -it shiftlog-api-1 pytest
# or
docker compose exec api pytest
```

Note: `shiftlog-api-1` is the name of the container running the Shiftlog API, which you need to confirm.

## API overview

### General

| Method | Path      | Description              |
| ------ | --------- | ------------------------ |
| GET    | `/health` | Check application health |

### Workers

| Method | Path            | Description         |
| ------ | --------------- | ------------------- |
| POST   | `/workers`      | Create a worker     |
| GET    | `/workers`      | List all workers    |
| GET    | `/workers/{id}` | Get a single worker |
| PUT    | `/workers/{id}` | Update a worker     |
| DELETE | `/workers/{id}` | Delete a worker     |

### Shifts

| Method | Path           | Description                                                                  |
| ------ | -------------- | ---------- |
| POST   | `/shifts`      | Create a shift (rejects overlapping shifts, 409)                             |
| GET    | `/shifts`      | List shifts, optionally filtered by `worker_id`, `start_after`, `end_before` |
| GET    | `/shifts/{id}` | Get a single shift                                                           |
| DELETE | `/shifts/{id}` | Delete a shift                                                           |
| PUT    | `/shifts/{id}` | Update a shift                      |

A shift conflicts with another shift for the _same worker_ when their time
ranges overlap. Back-to-back shifts (one ending exactly when the next
starts) are not conflicts.

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

## Getting Started / Testing Examples 🧪

### 1. Create a Worker (`POST /workers`)

```bash
curl -X 'POST' http://localhost:8000/workers -H "Content-Type: application/json" -d '{
"name": "Hikari",
"role": "Rubber Duck"
}'
```

**Response (201 Created):**

```json
{
  "id": 1,
  "name": "Hikari",
  "role": "Rubber Duck"
}
```

**Error (422 Unprocessable Entity):**

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "role"],
      "msg": "Field required",
      "input": {
        "name": "Hikari"
      }
    }
  ]
}
```

### 2. List all Workers (`GET /workers`)

```bash
curl -X GET http://localhost:8000/workers
```

**Response (200 OK):**

```json
[
  {
    "name": "Hikari",
    "role": "Rubber Duck",
    "id": 3
  }
]
```

### 3. Get a Single Worker (`GET /workers/{id}`)

```bash
curl -X GET http://localhost:8000/workers/1
```

**Response (200 OK):**

```json
{
  "name": "Hikari",
  "role": "Rubber Duck",
  "id": 1
}
```

**Error (404 Not Found):**

```json
{
  "detail": "Worker not found"
}
```

**Error (422 Unprocessable Entity):**

```json
{
  "detail": [
    {
      "type": "int_parsing",
      "loc": ["path", "worker_id"],
      "msg": "Input should be a valid integer, unable to parse string as an integer",
      "input": "not-an-int"
    }
  ]
}
```

### 4. Update a Worker (`PUT /workers/{id}`)

```bash
curl -X 'PUT' \
  'http://localhost:8000/workers/1' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Hikari",
    "role": "Rubber Duck"
  }'
```

**Response (200 OK):**

```json
{
  "id": 1,
  "name": "Hikari",
  "role": "Rubber Duck"
}
```

**Error (404 Not Found):**

```json
{
  "detail": "Worker not found"
}
```

**Error (422 Unprocessable Entity):**

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "role"],
      "msg": "Field required",
      "input": {
        "name": "Hikari"
      }
    }
  ]
}
```

### 5. Delete a Worker (`DELETE /workers/{id}`)

```bash
curl -X 'DELETE' \
  'http://localhost:8000/workers/1' \
  -H 'accept: */*'
```

**Response (204 No Content):**

```

```

**Error (404 Not Found):**

```json
{
  "detail": "Worker not found"
}
```

### 6. Create a Shift (`POST /shifts`)

```bash
curl -X 'POST' \
  'http://localhost:8000/shifts' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '  {
    "worker_id": 1,
    "start_time": "2026-08-11T13:06:46.203Z",
    "end_time": "2026-08-11T13:18:32.517Z"
  }'
```

**Response (201 Created):**

```json
{
  "worker_id": 1,
  "start_time": "2026-08-11T13:06:46.203Z",
  "end_time": "2026-08-11T13:18:32.517Z",
  "id": 1
}
```

**Error (404 Not Found):**

```json
{
  "detail": "Worker not found"
}
```

**Error (409 Conflict):**

```json
{
  "detail": "Shift conflicts with existing shift(s) for this worker: 2"
}
```

**Error (422 Unprocessable Entity):**

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "end_time"],
      "msg": "Field required",
      "input": {
        "worker_id": 1,
        "start_time": "2026-08-11T13:06:46.203Z"
      }
    }
  ]
}
```

### 7. List shifts, optionally filtered by `worker_id`, `start_after`, `end_before` (`GET /shifts`)

```bash
curl -X 'GET' \
  'http://localhost:8000/shifts' \
  -H 'accept: application/json'
```

**Response (200 OK):**

```json
[
  {
    "worker_id": 1,
    "start_time": "2026-08-11T13:06:46.203000",
    "end_time": "2026-08-11T13:18:32.517000",
    "id": 1,
    "created_at": "2026-08-11T13:10:58.598051"
  }
]
```

**Error (422 Unprocessable Entity):**

```json
{
  "detail": [
    {
      "type": "datetime_from_date_parsing",
      "loc": ["query", "start_after"],
      "msg": "Input should be a valid datetime or date, invalid character in year",
      "input": "not-a-date",
      "ctx": {
        "error": "invalid character in year"
      }
    }
  ]
}
```

### 8. Get a Single Shift (`GET /shifts/{id}`)

```bash
curl -X 'GET' \
  'http://localhost:8000/shifts/1' \
  -H 'accept: application/json'
```

**Response (200 OK):**

```json
{
  "worker_id": 1,
  "start_time": "2026-08-11T13:06:46.203000",
  "end_time": "2026-08-11T13:18:32.517000",
  "id": 1,
  "created_at": "2026-08-11T13:10:58.598051"
}
```

**Error (404 Not Found):**

```json
{
  "detail": "Shift not found"
}
```

### 9. Delete a Shift (`DELETE /shifts/{id}`)

```bash
curl -X 'DELETE' \
  'http://localhost:8000/shifts/1' \
  -H 'accept: */*'
```

**Response (204 Success):**

```

```

**Error (404 Not Found):**

```json
{
  "detail": "Shift not found"
}
```

### 10. Update a Shift (`PUT /shifts/{id}`)

```bash
curl -X 'PUT' \
  'http://localhost:8000/shifts/1' \
  -H 'Content-Type: application/json' \
  -d '{
    "worker_id": 1,
    "start_time": "2026-08-11T13:00:00.203Z",
    "end_time": "2026-08-11T17:18:00.517Z"
  }'
```

**Response (200 OK):**

```json
{
  "worker_id": 1,
  "start_time": "2026-08-11T13:00:00.203Z",
  "end_time": "2026-08-11T17:18:00.517Z",
  "id": 1,
  "created_at": "2026-08-11T17:30:00.598Z",
  "duration_hours": 4.3
}
```

**Error (404 Not Found) - Shift doesn't exist:**

```json
{
  "detail": "Shift not found"
}
```

**Error (404 Not Found) - Worker doesn't exist:**

```json
{
  "detail": "Worker not found"
}
```

**Error (409 Conflict):**

```json
{
  "detail": "Shift conflicts with existing shift(s) for this worker: 2"
}
```

### ASSUMPTIONS:

- It is assumed that the port `8000` is available on the host machine.

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

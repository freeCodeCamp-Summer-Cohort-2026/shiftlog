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

| Method | Path            | Description         |
| ------ | --------------- | ------------------- |
| POST   | `/workers`      | Create a worker     |
| GET    | `/workers`      | List all workers    |
| GET    | `/workers/{id}` | Get a single worker |

### Shifts

| Method | Path           | Description                                                                  |
| ------ | -------------- | ---------------------------------------------------------------------------- |
| POST   | `/shifts`      | Create a shift (rejects overlapping shifts, 409)                             |
| GET    | `/shifts`      | List shifts, optionally filtered by `worker_id`, `start_after`, `end_before` |
| GET    | `/shifts/{id}` | Get a single shift                                                           |
| DELETE | `/shifts/{id}` | Delete a shift                                                               |

A shift conflicts with another shift for the _same worker_ when their time
ranges overlap. Back-to-back shifts (one ending exactly when the next
starts) are not conflicts.

## Getting Started / Testing Examples 🧪

### 1. Create a Worker (`POST /workers`)

```bash
curl -X POST http://localhost:8000/workers -H "Content-Type: application/json" -d '{
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

**Error (400 Bad Request):**

```json
{
  "detail": [
    {
      "loc": ["string", 0],
      "msg": "string",
      "type": "string"
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
      "loc": ["string", 0],
      "msg": "string",
      "type": "string"
    }
  ]
}
```

### 4. Create a Shift (`POST /shifts`)

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
      "loc": ["string", 0],
      "msg": "string",
      "type": "string"
    }
  ]
}
```

### 5. List shifts, optionally filtered by `worker_id`, `start_after`, `end_before` (`GET /shifts`)

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
      "loc": ["string", 0],
      "msg": "string",
      "type": "string"
    }
  ]
}
```

### 6. Get a Single Shift (`GET /shifts/{id}`)

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

### 7. Delete a Shift (`DELETE /shifts/{id}`)

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

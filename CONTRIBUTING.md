# Contributing to ShiftLog

Thanks for picking up an issue during the sprint phase. This doc covers how
to claim an issue, submit a PR, and run things locally.

## Claiming an issue

1. Find an open issue that isn't already claimed (check for a "claimed by"
   comment).
2. Comment on the issue to claim it, e.g. "Claiming this one!"
3. You have **48 hours** from your claim comment to open a PR (a draft PR
   counts). If 48 hours pass with no PR, the issue is considered released
   and anyone else can claim it.
4. If you need more time, just say so in a comment before the 48 hours are
   up - a quick heads-up is all it takes.

Only work one issue at a time so everyone gets a fair shot at something to
ship.

## Making changes

1. Fork the repo (or create a branch if you have write access).
2. Create a branch named something like `<your-github-username>/<short-description>`.
3. Make your change. Keep PRs scoped to the issue you claimed - if you spot
   something else worth fixing, open a separate issue for it rather than
   bundling it in.
4. Add or update tests that cover your change.
5. Run the test suite locally before opening your PR (see below).
6. Open a PR against `main` and reference the issue it closes, e.g.
   `Closes #12`.

## Running tests locally

Tests run against an in-memory SQLite database, so you don't need Docker or
Postgres running to work on most issues:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -v
```

If your change touches `docker-compose.yml`, the Dockerfile, or anything
that depends on real Postgres behavior, also sanity-check it end-to-end:

```bash
cp .env.example .env
docker-compose up --build
```

You can also run the tests against the actual instance of Shiftlog, be sure it is a development instance, because tests may cause data changes or loss:

```bash
docker exec -it shiftlog-api-1 pytest
# or
docker compose exec api pytest
```
Note: `shiftlog-api-1` is the name of the container running the Shiftlog API, which you need to confirm.

Optionally, you can produce an HTML report from `pytest`:

```bash
mkdir -p reports
docker exec -it shiftlog-api-1 pip install pytest-html
docker exec -it shiftlog-api-1 pytest --html=report.html --self-contained-html
docker cp shiftlog-api-1:report.html reports/
# open reports/report.html in your browser
```

CI runs `pytest` on every push and pull request (see
`.github/workflows/ci.yml`) - PRs need a green check before merge.

## Code style

- Keep functions small and readable over clever. This is a training
  exercise, not a golf competition.
- Match the existing patterns in the file you're editing (e.g. how routers
  use `Depends(get_session)`, how errors raise `HTTPException`).
- Prefer clear error messages over generic ones.

## Labels

- `difficulty:easy` / `difficulty:medium` / `difficulty:hard` - rough sizing
  to help you pick something that matches your comfort level.
- `area:api` / `area:data` / `area:tests` / `area:docs` - which part of the
  codebase the issue touches.

If anything here is unclear, ask in the issue thread or in the cohort
Discord - don't guess and burn your 48 hours on the wrong approach.

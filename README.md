# AI-Powered Personalized Learning Path Recommender — Backend

Phase 1 of the architecture: the **deterministic core**. Profile, skill taxonomy,
prerequisite DAG, resource catalogue, learning paths, assessments, progress and
feedback — all of it computed in plain code, with no model in the loop.

The recommendation engine, skill-gap engine, path generator and LLM layer are
deliberately **not** implemented yet. The tables and fields they will write to
(`recommendations.rationale_trace`, `learning_path_items.rationale_trace`,
`skills.embedding`, `resources.embedding`) already exist so those phases slot in
without a migration of existing data.

## Stack

FastAPI · Pydantic v2 · SQLAlchemy 2.0 (async, asyncpg) · PostgreSQL 16 + pgvector ·
Alembic · Redis (provisioned, unused until the caching phase) · Docker Compose

## Quick start — Docker

```bash
docker compose up
```

That builds the API image, waits for Postgres, runs `alembic upgrade head`, seeds
the bootstrap admin, and serves on <http://localhost:8000>.

- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

If ports 5432 / 6379 / 8000 are already taken on your machine, copy `.env.example`
to `.env` at the repo root and change `POSTGRES_PORT`, `REDIS_PORT` or `API_PORT`.
Only the host-side mapping changes; container-internal ports stay fixed.

## Quick start — local

```bash
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
```

```bash
cp backend/.env.example backend/.env
```

```bash
docker compose up -d postgres redis
```

```bash
cd backend && .venv/bin/alembic upgrade head && .venv/bin/python -m app.db.seed
```

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload
```

Python 3.12 is required — 3.13+ has no wheels yet for some pinned dependencies.

## Tests

```bash
cd backend && .venv/bin/python -m pytest
```

`tests/test_smoke.py` needs nothing. `tests/test_api_integration.py` runs in-process
against the real database and skips itself if none is reachable.

## Layering

```
routers/        HTTP only — auth guard, serialisation, status codes
   ↓
services/       business rules, transaction boundary, domain exceptions
   ↓
repositories/   SQLAlchemy queries; flush but never commit
   ↓
models/ + db/   ORM and engine/session
```

Routers hold no logic. Services raise `app.core.errors.*`, which the handlers in
`app/main.py` render as RFC 7807 `application/problem+json`. Repositories never
raise HTTP errors.

## Design notes

**UUID primary keys** everywhere, generated app-side (`uuid4`) with a
`gen_random_uuid()` server default so rows inserted outside the ORM still work.

**Timestamps are computed in Python**, not by a SQL `onupdate`. A SQL-expression
`onupdate` leaves the attribute expired after flush, and refreshing it lazily
while serialising the response raises `MissingGreenlet` on an async session.
`server_default` is kept for non-ORM inserts.

**Relationships are eagerly loaded** wherever a response schema nests them, for
the same reason: there is no lazy loading available at serialisation time.

**Prerequisite cycles are rejected at write time.** Adding `skill → prerequisite`
is refused when `skill` already appears in the prerequisite closure of
`prerequisite` (recursive CTE, depth-bounded). Correctness here is not something
to delegate to a model.

**Ownership is checked as a 404, not a 403**, so a non-owner cannot probe which
ids exist.

**Assessment grading is exact-match** against the stored key; multiple-choice is
order-insensitive; short-answer is never auto-marked correct and is left for a
reviewer.

**Progress is event-sourced** — `user_progress` is append-only and every summary
is derived from it. Item status is a denormalised convenience kept in step by the
service.

## Layout

```
.
├── docker-compose.yml
├── .env.example                 # host port mappings for compose
├── infra/postgres/init.sql      # vector, pgcrypto, pg_trgm
└── backend/
    ├── Dockerfile
    ├── docker/entrypoint.sh     # wait for db → migrate → seed → serve
    ├── alembic.ini
    ├── alembic/
    │   ├── env.py               # async migrations, pgvector render hook
    │   └── versions/
    ├── requirements.txt
    ├── requirements-dev.txt
    ├── pytest.ini
    ├── .env.example
    ├── app/
    │   ├── main.py              # app factory, middleware, error handlers
    │   ├── core/                # config, logging, security, errors, deps
    │   ├── db/                  # session, alembic metadata surface, seed
    │   ├── models/              # 17 tables
    │   ├── schemas/             # Pydantic request/response
    │   ├── repositories/        # data access
    │   ├── services/            # business logic
    │   └── routers/             # HTTP
    └── tests/
```

## Entities

| Group | Tables |
|---|---|
| Identity | `users`, `learner_profiles` |
| Taxonomy | `skills`, `prerequisites`, `user_skills` |
| Goals | `learning_goals`, `learning_goal_skills` |
| Catalogue | `resources`, `resource_skills` |
| Paths | `learning_paths`, `learning_path_items` |
| Assessment | `assessments`, `assessment_questions`, `assessment_results` |
| Signals | `user_progress`, `feedback`, `recommendations` |

## Endpoints

All under `/api/v1`; health probes sit outside the prefix.

| Area | Endpoints |
|---|---|
| Health | `GET /health`, `/health/live`, `/health/ready` |
| Auth | `POST /auth/register`, `/auth/login`, `GET /auth/me` |
| Users | `GET/POST /users`, `GET/PATCH /users/me`, `GET/PATCH/DELETE /users/{id}` |
| Profile | `GET/POST/PUT/PATCH/DELETE /profile` |
| Learner skills | `GET/POST/PUT /me/skills`, `GET/PATCH/DELETE /me/skills/{skill_id}` |
| Skills | `GET/POST /skills`, `GET/PATCH/DELETE /skills/{id}` |
| Graph | `GET/POST /skills/{id}/prerequisites`, `GET /skills/{id}/graph`, `PATCH/DELETE /prerequisites/{edge_id}` |
| Goals | `GET/POST /goals`, `GET/PATCH/DELETE /goals/{id}`, `POST /goals/{id}/skills`, `PATCH/DELETE /goals/{id}/skills/{skill_id}` |
| Resources | `GET/POST /resources`, `GET/PATCH/DELETE /resources/{id}`, `GET/POST /resources/{id}/skills`, `PATCH/DELETE /resources/{id}/skills/{skill_id}` |
| Paths | `GET/POST /learning-paths`, `GET /learning-paths/active`, `GET/PATCH/DELETE /learning-paths/{id}`, `GET/POST /learning-paths/{id}/items`, `PATCH/DELETE /learning-paths/{id}/items/{item_id}` |
| Assessments | `GET/POST /assessments`, `GET/PATCH/DELETE /assessments/{id}`, `GET/POST /assessments/{id}/questions`, `PATCH/DELETE /assessments/{id}/questions/{qid}`, `POST /assessments/{id}/submit` |
| Results | `GET /me/assessment-results`, `GET /me/assessment-results/{id}` |
| Progress | `POST/GET /progress/events`, `GET /progress/summary` |
| Feedback | `GET/POST /feedback`, `GET/PATCH/DELETE /feedback/{id}` |
| Recommendations | `GET /recommendations`, `GET/DELETE /recommendations/{id}`, `PATCH /recommendations/{id}/status`, `POST /users/{user_id}/recommendations` (admin) |

Catalogue writes (skills, prerequisites, resources, assessments) require the
`admin` role. Everything scoped to a learner is filtered by the authenticated
user at the repository level.

## Next phases

Skill-gap engine → retrieval → ranking → path generator → LLM extraction and
explanation, in that order. The engines land in `app/engines/` as pure functions
so they are unit-testable without a database.

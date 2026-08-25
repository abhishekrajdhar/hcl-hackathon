# AI-Powered Personalized Learning Path Recommender

A learner states a goal, the system works out what they already know, computes
the gap against a prerequisite graph, builds an ordered roadmap over a resource
catalogue, tracks progress, adapts as evidence arrives, and explains itself — in
a dashboard and through a conversational assistant.

## The determinism boundary

The core design rule, visible everywhere in the code: **the deterministic engine
decides, the model only writes prose.**

Every decision that has a right answer — prerequisite ordering, gap size,
resource ranking, roadmap phasing, assessment scoring, mastery level, adaptive
branching — is computed in pure Python in `app/engines/`. No DB, no clock, no
network, no model. Same inputs, same outputs, unit-testable without a database
and auditable after the fact.

The LLM is used only where natural language is genuinely required:

| The model does | The model never does |
|---|---|
| Extract a structured profile from free text | Decide a proficiency, gap or score |
| Draft candidate assessment questions | Grade an answer |
| Rephrase a grounded explanation | Invent the facts it explains |
| Write the assistant's final reply | Choose which application data to fetch |

Both edges are fenced. Extracted profiles and generated questions are validated
against Pydantic contracts before use — a malformed or unkeyed question is
rejected, never scored. Generated prose passes `engines/explanation/grounding.py`,
which rejects any percentage that does not match the structured evidence and any
skill-like phrase absent from it.

## How a recommendation is produced

```
profile + goal
   → skill_gap/analyzer      what is missing, in prerequisite order
   → search (pgvector)       candidate resources, semantically retrieved
   → recommendation/scoring  weighted hybrid rank + readiness gate
   → path/generator          phased roadmap with a schedule
   → explanation             rationale, grounded against the evidence
```

Two details worth knowing. Gaps are **not** sorted by size — a prerequisite
always precedes what depends on it (priority-aware topological sort). And ranking
applies a **readiness gate**: a resource whose prerequisites the learner does not
meet is demoted or excluded, so recommendations match the learner's current
stage rather than just being popular or similar.

Assessment results feed `adaptive/` (fixed threshold bands), which updates
proficiency via an evidence-weighted blend and can trigger a path regeneration.

## Stack

**Backend** — FastAPI · Pydantic v2 · SQLAlchemy 2.0 (async, asyncpg) ·
PostgreSQL 16 + pgvector · Alembic · Redis (provisioned, unused until the
caching phase) · Docker Compose

**Frontend** — Next.js 15 (App Router) · React 19 · TypeScript · Tailwind ·
Recharts

**Models** — LLM provider is `mock | claude | openai`, embeddings are
`mock | sentence_transformer`, both chosen from settings and never hard-coded in
callers. Both default to `mock`, so the whole stack runs in dev and CI with no
API key and no torch.

## Quick start — Docker

```bash
docker compose up
```

Builds the API image, waits for Postgres, runs `alembic upgrade head`, seeds the
skill graph, resource catalogue and bootstrap admin, and serves on
<http://localhost:8000>.

- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

Compose runs the backend only; start the frontend separately (below).

If ports 5432 / 6379 / 8000 are already taken, copy `.env.example` to `.env` at
the repo root and change `POSTGRES_PORT`, `REDIS_PORT` or `API_PORT`. Only the
host-side mapping changes; container-internal ports stay fixed.

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

For real semantic embeddings instead of the mock, install the optional extra and
set `EMBEDDING_PROVIDER=sentence_transformer`:

```bash
cd backend && .venv/bin/pip install -r requirements-embeddings.txt
```

It pulls in torch, which is why it is deliberately not in the default image.
`EMBEDDING_DIM` is the pgvector column width — changing it needs a migration.

## Quick start — frontend

```bash
cd frontend && npm install
```

```bash
cd frontend && BACKEND_URL=http://localhost:8000 npm run dev
```

Serves on <http://localhost:3000>. `next.config.ts` rewrites `/api/*` to
`BACKEND_URL`, so the browser stays same-origin and there is no CORS credential
handling. Signed out, the dashboard renders a bundled demo dataset that is
shape-identical to the derived API response; sign in with the seeded admin (or
any registered account) to see real data.

## Tests

```bash
cd backend && .venv/bin/python -m pytest
```

24 test files. Engine tests are separate from API tests by design: everything in
`app/engines/` is pure, so its tests need no database at all. `tests/test_smoke.py`
needs nothing either. The API tests run in-process against the real database and
skip themselves if none is reachable.

## Layering

```
routers/        HTTP only — auth guard, serialisation, status codes
   ↓
services/       business rules, transaction boundary, domain exceptions
   ↓
repositories/   SQLAlchemy queries; flush but never commit
   ↓
models/ + db/   ORM and engine/session

engines/        pure decision logic — called by services, depends on nothing
llm/            provider-agnostic transport + structured-output contracts
embeddings/     provider-agnostic vectors + query cache
```

Routers hold no logic. Services raise `app.core.errors.*`, which the handlers in
`app/main.py` render as RFC 7807 `application/problem+json`. Repositories never
raise HTTP errors.

`engines/` depends on plain data only — enums, frozen dataclasses and Pydantic
schemas — never on a session, a repository or a query. Nothing in it opens a
connection, reads the clock or calls a provider, so its tests need no database
and its output is reproducible. (One seam to keep an eye on:
`engines/chat/compose.py` imports the `ToolResult` dataclass from
`services/chat_tools.py`, so that one module points back up a layer for a type.)

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
`prerequisite` (recursive CTE, depth-bounded). The seed loader goes through the
same check, so the declarative seed data cannot corrupt the DAG even if edited
carelessly.

**Ownership is checked as a 404, not a 403**, so a non-owner cannot probe which
ids exist.

**Assessment grading is exact-match** against the stored key; multiple-choice is
order-insensitive; short-answer is never auto-marked correct and is left for a
reviewer.

**Progress is event-sourced** — `user_progress` is append-only and every summary
is derived from it. Item status is a denormalised convenience kept in step by the
service.

**Conversation memory and application state are strictly separate.** The messages
table stores dialogue only; every application fact is re-fetched through a tool
each turn. The assistant cannot drift from stored state because it holds none —
and when a tool returns nothing, the reply says so rather than filling the gap.

**Provider credentials are validated lazily.** An unconfigured `claude`/`openai`
provider fails at call time with a clear message rather than at import, so the
app still boots.

## The assistant

`services/chat_service.py` is deterministic control flow around a generative
step:

```
message → detect intent (rule-based) → select tools → run tools (real services)
        → compose grounded reply → optional LLM rephrase (grounded) → persist turn
```

Intent detection is pure regex over ordered, most-specific-first patterns — the
model never decides what to fetch.

A learner rarely says one thing at a time, and least of all out loud. On top of
the single intent, every turn is also scanned for a **time budget** and for
**skills the learner claims to have**, because "I want to be an ML engineer, I
have an hour a day and I already know Python" is all three at once. Both are
pure functions in `engines/chat/intent.py`: the budget is normalised to hours
per week (an hour a day → 7), and skill claims are resolved against the
catalogue, with anything that does not resolve to exactly one skill dropped
rather than guessed at. A claim never overwrites an existing record — an
assessment result is harder evidence than a passing remark, so self-report only
fills a blank.

That turns goal-setting into a real onboarding exchange:

> **"I want to become a machine learning engineer, but I only have about an hour
> a day and I'm already comfortable with Python."**
>
> Got it — your goal is to become a machine learning engineer. Since you're
> already comfortable with Python, I won't start you on beginner Python
> material. With roughly 7 hours a week, I'd suggest starting with Linear
> Algebra and Statistics. Before I finalise the roadmap, can I ask how
> comfortable you are with Linear Algebra?

Every clause is earned: Python came from the sentence, 7 hours from arithmetic
on it, and Linear Algebra from `get_goal_prerequisites` — the prerequisites of
the goal skill that the learner has no record for. When the goal does not
resolve to a catalogue skill, the closing question is simply not asked, rather
than invented.

The nine tools available to it:

| Tool | Returns |
|---|---|
| `get_learner_profile` | Goal, role, weekly hours, recorded skills |
| `get_skill_gaps` | Skills still needing work, current vs required |
| `get_current_learning_path` | Active roadmap: phases, milestones, status |
| `get_recommendations` | Current recommended resources |
| `get_progress` | Items completed, time spent, completion % |
| `get_next_action` | The single next step |
| `search_resources` | Catalogue search for a query |
| `update_learning_progress` | Record a completion or score, adapt the path |
| `get_goal_prerequisites` | What the goal rests on, split into met and unknown |

## Talking to it

The assistant can be driven by voice. The loop wraps the pipeline above without
altering it:

```
speak → speech-to-text → (the unchanged /chat pipeline) → reply → text-to-speech
```

A spoken turn calls exactly the same `send` as a typed one, so the two input
modes cannot drift apart — the intent engine, the tools and the grounding check
are identical either way, and the transcript is the same conversation.

Speech runs in the **browser**, through the platform's own Web Speech API: no
API key, no extra dependency, no backend route, in keeping with the way the rest
of the app defaults to providers that work with nothing configured. The seam in
`lib/voice/speech.ts` is narrow on purpose (start/stop/speak/cancel) so a
server-side provider — Whisper for transcription, a TTS endpoint for audio —
can replace it without touching the hook or the UI.

Details that matter when a coach talks rather than types:

- **Barge-in.** Speaking over a reply cancels it, which also stops the
  microphone hearing the synthesiser.
- **Replies are rewritten for the ear**, not the eye: `85%` is spoken as "85
  percent", `1 skill(s)` as "1 skill" and `2 skill(s)` as "2 skills", and URLs
  become "the link on screen".
- **Graceful degradation.** A browser with no speech support keeps the text
  chat and says so; a denied microphone shows what to do and returns to idle
  rather than hanging on "listening".

**Privacy:** `speechSynthesis` runs on the device, but browser speech
*recognition* does not — Chrome and Safari stream microphone audio to their own
speech services to transcribe it. The UI states this before the microphone is
ever opened.

## Layout

```
.
├── docker-compose.yml
├── .env.example                 # host port mappings for compose
├── infra/postgres/init.sql      # vector, pgcrypto, pg_trgm
├── backend/
│   ├── Dockerfile
│   ├── docker/entrypoint.sh     # wait for db → migrate → seed → serve
│   ├── alembic/versions/        # 6 migrations
│   ├── requirements{,-dev,-embeddings}.txt
│   ├── app/
│   │   ├── main.py              # app factory, middleware, error handlers
│   │   ├── core/                # config, logging, security, errors, deps
│   │   ├── db/
│   │   │   ├── seed.py          # idempotent bootstrap
│   │   │   └── seeds/           # declarative skill graph + catalogue
│   │   ├── models/              # 21 tables
│   │   ├── schemas/             # Pydantic request/response
│   │   ├── repositories/        # data access
│   │   ├── services/            # business logic (27 modules)
│   │   ├── engines/             # pure decision logic
│   │   │   ├── skill_graph/     # DAG algorithms
│   │   │   ├── skill_gap/       # gap analysis + ordering
│   │   │   ├── recommendation/  # hybrid scoring + readiness gate
│   │   │   ├── path/            # roadmap generator
│   │   │   ├── adaptive/        # threshold bands, proficiency update
│   │   │   ├── assessment/      # mastery, question bank
│   │   │   ├── profile/         # proficiency arithmetic, validation
│   │   │   ├── explanation/     # templates + grounding guard
│   │   │   └── chat/            # intent detection, reply composition
│   │   ├── llm/                 # base, factory, providers, prompts, schemas
│   │   ├── embeddings/          # base, factory, providers, cache, text
│   │   └── routers/             # HTTP
│   └── tests/                   # 24 files, engines tested without a DB
└── frontend/
    ├── next.config.ts           # /api/* → BACKEND_URL rewrite
    └── src/
        ├── app/                 # landing page + /dashboard
        ├── components/
        │   ├── landing/         # hero, features, showcase, testimonials
        │   ├── dashboard/       # 11 tabs + chat, roadmap, knowledge graph
        │   ├── charts/          # ring, radar, bars, activity
        │   └── ui/              # primitives
        └── lib/
            ├── api/             # typed endpoint layer over one fetch client
            ├── voice/           # browser speech-to-text and text-to-speech
            ├── hooks/           # auth, chat, voice, dashboard data, theme, toast
            └── derive.ts        # API response → dashboard view model
```

## Seed data

`python -m app.db.seed` is idempotent and safe on every deploy. It writes the
bootstrap admin plus a working knowledge graph: **10 categories, 49 skills,
76 prerequisite edges, 25 resources**. Edges reference skills by slug and are
resolved and cycle-checked at load time.

## Entities

| Group | Tables |
|---|---|
| Identity | `users`, `learner_profiles` |
| Taxonomy | `skill_categories`, `skills`, `prerequisites`, `user_skills` |
| Goals | `learning_goals`, `learning_goal_skills` |
| Catalogue | `resources`, `resource_skills`, `resource_prerequisites` |
| Paths | `learning_paths`, `learning_path_items` |
| Assessment | `assessments`, `assessment_questions`, `assessment_results` |
| Signals | `user_progress`, `feedback`, `recommendations` |
| Conversation | `conversations`, `conversation_messages` |

`skills.embedding` and `resources.embedding` are pgvector columns; ranking
rationale is persisted in `recommendations.rationale_trace` and
`learning_path_items.rationale_trace`, so a past recommendation stays auditable.

## Endpoints

All under `/api/v1`; health probes sit outside the prefix.

| Area | Endpoints |
|---|---|
| Health | `GET /health`, `/health/live`, `/health/ready` |
| Auth | `POST /auth/register`, `/auth/login`, `GET /auth/me` |
| Users | `GET/POST /users`, `GET/PATCH /users/me`, `GET/PATCH/DELETE /users/{id}` |
| Profile | `GET/POST/PATCH/DELETE /profile`, `GET/PUT/PATCH /profile/{user_id}`, `GET /profile/{user_id}/validate`, `POST /profile/{user_id}/ingest` |
| Profile extraction | `POST /profile/extract` (free text → structured profile) |
| Profile skills | `GET/POST /profile/{user_id}/skills`, `GET/PUT/DELETE /profile/{user_id}/skills/{skill_id}` |
| Learner skills | `GET/POST/PUT /me/skills`, `GET/PATCH/DELETE /me/skills/{skill_id}` |
| Categories | `GET/POST /skill-categories`, `PATCH/DELETE /skill-categories/{id}` |
| Skills | `GET/POST /skills`, `GET/PATCH/DELETE /skills/{id}` |
| Graph | `GET /skills/{id}/prerequisites\|dependents\|dependencies\|prerequisite-tree\|graph`, `POST /skills/{id}/prerequisites`, `PATCH/DELETE /prerequisites/{edge_id}`, `GET /skills/graph/cycles` |
| Sequencing | `POST /skills/learning-sequence`, `POST /skills/validate-order` |
| Goals | `GET/POST /goals`, `GET/PATCH/DELETE /goals/{id}`, `POST /goals/{id}/skills`, `PATCH/DELETE /goals/{id}/skills/{skill_id}` |
| Resources | `GET/POST /resources`, `GET/PUT/PATCH/DELETE /resources/{id}`, `GET/POST /resources/{id}/skills`, `PUT/DELETE /resources/{id}/skills/{skill_id}`, `GET/POST /resources/{id}/prerequisites`, `DELETE /resources/{id}/prerequisites/{skill_id}` |
| Embedding | `POST /resources/embed-all`, `POST /resources/{id}/embed` |
| Search | `POST /search/semantic`, `POST /search/for-goal`, `GET /search/for-skill/{skill_id}`, `GET /search/for-profile` |
| Skill gap | `POST /skill-gap/analyze` |
| Path generation | `POST /learning-path/generate`, `GET /learning-path/{user_id}`, `POST /learning-path/{path_id}/regenerate` |
| Paths (CRUD) | `GET/POST /learning-paths`, `GET /learning-paths/active`, `GET/PATCH/DELETE /learning-paths/{id}`, `GET/POST /learning-paths/{id}/items`, `PATCH/DELETE /learning-paths/{id}/items/{item_id}` |
| Assessments | `GET/POST /assessments`, `POST /assessments/generate`, `GET/PATCH/DELETE /assessments/{id}`, `GET/POST /assessments/{id}/questions`, `PATCH/DELETE /assessments/{id}/questions/{qid}`, `POST /assessments/{id}/submit`, `GET /assessments/{id}/results` |
| Results | `GET /me/assessment-results`, `GET /me/assessment-results/{id}` |
| Adaptive | `POST /adaptive/update` |
| Progress | `POST/GET /progress/events`, `GET /progress/summary` |
| Feedback | `GET/POST /feedback`, `GET/PATCH/DELETE /feedback/{id}` |
| Recommendations | `GET/POST /recommendations`, `GET/DELETE /recommendations/{id}`, `PATCH /recommendations/{id}/status`, `POST /recommendations/{id}/explanation`, `POST /users/{user_id}/recommendations` (admin) |
| Chat | `POST /chat`, `GET /chat/conversations`, `GET /chat/conversations/{id}` |

Catalogue writes (skills, prerequisites, resources, assessments), user
administration and cross-user recommendation generation require the `admin`
role. Everything scoped to a learner is filtered by the authenticated user at
the repository level.

## Frontend

A landing page and a signed-in dashboard with eleven tabs — Overview, Next
Action, Roadmap, Learning Path, Skill Progress, Knowledge Graph, Milestones,
Recommended, Assessments, Activity, AI Assistant.

The **Knowledge Graph** tab draws the prerequisite DAG itself: a layered
top-to-bottom layout where a skill never appears above something it depends on,
so reading downwards is a valid learning order. Nodes are coloured by mastery
using the backend's own skill-level bands (`SKILL_SKIP_INTRO` / `SKILL_REMEDIAL`
from `engines/adaptive/decisions.py`), so a node's colour cannot disagree with
the adaptive engine. Selecting one highlights its full prerequisite chain and
everything it unlocks, and answers three questions — why it is on your path,
what is needed before it, and what it opens up — from graph structure and the
dependency endpoint rather than from generated text. The layout is a pure
function in `lib/graph-view.ts`: longest-path ranking, then barycentre ordering
to reduce edge crossings.

UI components never call `fetch` directly. Everything goes through the typed
endpoint functions in `lib/api/`, built on a single client that owns the bearer
token and turns RFC 7807 problem responses into a typed `ApiError`. `derive.ts`
converts API responses into the dashboard view model, and the demo dataset
matches that shape exactly — so demo and live mode exercise identical rendering
code.

## Not built yet

Redis is provisioned and wired into compose but nothing reads it; response and
embedding caching is the open item. Beyond that: reviewer tooling for
short-answer grading, and feedback signals feeding back into ranking weights.

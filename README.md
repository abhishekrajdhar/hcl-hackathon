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
PostgreSQL 16 + pgvector · Alembic · Redis (shared query-embedding cache) ·
Docker Compose

**Frontend** — Next.js 15 (App Router) · React 19 · TypeScript · Tailwind ·
Recharts · Three.js (react-three-fiber) · Inter + Space Grotesk

**Models** — LLM provider is `mock | claude | openai`, embeddings are
`mock | openai | sentence_transformer`, both chosen from settings and never
hard-coded in callers. Both default to `mock`, so the whole stack runs in dev
and CI with no API key and no torch.

**Using OpenAI.** One key drives both halves. Put it in `backend/.env` (which
is gitignored) or export it, then:

```bash
export OPENAI_API_KEY=sk-...
./scripts/use-openai.sh
```

That sets `LLM_PROVIDER=openai` and `EMBEDDING_PROVIDER=openai`, recreates the
API with the key passed through from your shell — never baked into the image or
a tracked file — and re-embeds the catalogue, which is required because
changing provider changes what the vectors mean.

Worth knowing: `text-embedding-3-small` accepts a `dimensions` parameter, so
the provider requests exactly `EMBEDDING_DIM` (384) and the vectors drop into
the existing pgvector column — **no migration**, and switching back to `mock`
stays a config change. Without a key the provider logs a warning and falls back
to the mock rather than failing to boot.

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
| `explain_skill_relationship` | How one skill depends on another in the graph |
| `suggest_careers` | Career directions for an uncertain learner (agentic, grounded) |

## The interface

The app is one dark, cinematic world rather than a dashboard. Design tokens
live in `app/globals.css`; **colour carries information**, roughly 70%
obsidian/graphite, 20% cyan/teal, 7% amber, 3% coral:

| Colour | Meaning |
|---|---|
| Cyan `#29E6D1` | Active — currently learning, interactive, selected |
| Teal `#0F8F87` | Available, healthy, secondary structure |
| Amber `#FFB84A` | Mastered, achievement, milestone |
| Coral `#FF6B6B` | Weak, needs attention |
| Steel `#607080` | Locked, undiscovered — the knowledge fog |

`STATE_COLOR` in `lib/graph-view.ts` and `STATE_HEX` in `GalaxyScene.tsx` both
read from this one set, so the 2D graph, the 3D world and the HUD cannot drift
apart.

The chrome is instrumentation, not cards: hairline edges, near-square corners,
corner brackets (`.hud`, `.hud-bracket`), uppercase tracked metadata
(`.label-meta`), tabular readouts, and Space Grotesk for display type. There is
no sidebar — a 68px rail expands on hover, and a 48px status strip carries the
goal, level, XP and pace. Nothing sits in a rounded card.

**The Learning Universe is the page**, not a widget on it: it opens full-bleed
at viewport height with every panel floating over it. Selecting a star eases
the camera toward it along its current bearing (so the world never spins behind
the learner), lights the prerequisite chain with charge packets travelling
prerequisite → dependent, and dims everything else.

XP and level are **derived, not stored** (`lib/xp.ts`) — pure functions of
completed items, proficiency and assessment performance, so the number can
never disagree with the work behind it.

There is **one palette and no theme switch**. A daylight variant would have
meant either a washed-out galaxy or overlay text that goes dark-on-dark over a
world that is always night — so the product commits to night and the whole
system gets simpler for it.

The landing page runs the **real engine**, not a mockup: its hero mounts the
same `GalaxyScene` with the demo graph, in ambient mode (drifting camera, no
selection, pointer events passing through). Sections below are an engine spec
sheet — numbered subsystems naming the actual modules, and the pipeline drawn
as a signal chain.

## Goal intelligence and career discovery

A learner's first message is read for what KIND of goal it is — career,
internship, transition, skill — and for uncertainty. "I don't know what I want
to do" routes to **career discovery** instead of the gap engine, which cannot
plan toward "I don't know".

Both are **agentic with a validated floor**. With a provider configured
(`LLM_PROVIDER=openai`), the model does the reasoning: it reads the goal
utterance, and for uncertain learners it proposes career directions from the
learner's signals and the real catalogue. What keeps it honest is the seam in
`services/discovery_service.py`:

```
signals → LLM → schema-validated proposal → grounded against the skill graph
        → unresolvable skills dropped, skill-less directions discarded
        → deterministic fallback if nothing survives
```

The model may propose a career, but it cannot invent the skills it requires —
every target skill is resolved against the catalogue, and each surviving
direction carries the exact target-skill vector the path generator plans from.
With no provider (or a failing one), a curated deterministic engine
(`engines/discovery/careers.py`) answers instead: degraded, never down.

Onboarding exposes all three intakes: describe the goal in a sentence, paste a
resume (read by the same extraction seam), or "not sure yet" → discovery.

**The graph grows to meet the goal.** The seeded catalogue cannot name every
destination, so a goal it lacks ("backend developer") is not a dead end: the
model designs that role's required-skill graph — reusing catalogue skills where
they fit, proposing new ones only where the catalogue is missing them — and
`services/role_graph_service.py` materialises the design with deterministic
code. New skills are real rows marked `origin: role_graph`; every prerequisite
edge goes through the cycle-checked graph API, so a cycle in the design is
refused, never written; and a second learner naming the same role converges on
the graph the first one grew. Milestones for skills with no catalogue content
become self-study items, so the path still plans. The fallback ladder beneath
it: exact catalogue match → model-designed graph → nearest curated role →
a 422 that routes to career discovery (which onboarding turns into an
automatic pivot rather than an error).

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
│   │   │   ├── recommendation/  # hybrid scoring, readiness gate, prior learning
│   │   │   ├── progress/        # learning-pace model
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
            ├── universe-layout.ts # pure 3D projection of the graph model
            ├── hooks/           # auth, chat, voice, dashboard data, theme, toast
            └── derive.ts        # API response → dashboard view model
```

## Seed data

`python -m app.db.seed` is idempotent and safe on every deploy. It writes the
bootstrap admin, a working knowledge graph — **10 categories, 49 skills,
76 prerequisite edges** — and the resource catalogue.

The catalogue is **real content**: 57 YouTube courses and lectures whose title,
channel and runtime were read from YouTube's own oEmbed endpoint and watch
page, not written by hand. A candidate that failed verification was dropped
rather than seeded with guessed metadata, so every URL resolves and every
`estimated_hours` is an actual runtime (261 hours in total, from freeCodeCamp,
3Blue1Brown, StatQuest, Andrej Karpathy, Corey Schafer and others). Refresh it
when videos change:

```bash
python scripts/refresh_catalogue.py   # re-reads YouTube
python scripts/gen_seed.py            # regenerates the seed
python -m app.db.seed                 # reconciles the database
```

Resource prerequisites are **derived from the skill graph** rather than written
twice, so the catalogue and the DAG cannot disagree about what gates what.
Introductory material (difficulty 1–2) is never gated — gating a beginner
course behind prerequisites is how a learner gets stuck.

Alongside the videos sit 8 project briefs and 3 checkpoints, which are
completed inside the app rather than on an external site.

Seeding **reconciles** existing rows rather than skipping them: a title,
runtime or prerequisite that changes in the seed lands on the next run, and the
row keeps its id so learning paths pointing at it stay valid.

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
| Review (admin) | `GET /assessment-reviews`, `POST /assessment-reviews/{result_id}` |
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

A landing page, dedicated `/login` and `/signup` routes, and a signed-in
dashboard with twelve sections — Learning Universe, Overview, Current Mission,
Roadmap, Learning Path, Skill Progress, Knowledge Graph, Milestones,
Recommended, Assessments, AI Coach, System.

Authentication is its own route rather than a form wearing the dashboard's
chrome: `/dashboard` redirects an unauthenticated visitor to `/login`, and
`/dashboard?demo=1` opens the bundled demo dataset with no account at all.

A learner who signs up goes to **`/onboarding`**, not to someone else's demo
journey. They describe the goal in one sentence — "I want to become a machine
learning engineer, I have about 8 hours a week and I already know Python" — and
that single message sets the goal, the weekly budget and the skills they
already have. `POST /learning-path/generate` then resolves the goal text to a
catalogue skill and plans the route to it, so nobody has to pick target skills
from a list. A goal that does not resolve returns a 422 naming the closest
matches rather than planning a confident, empty path.
Both `POST /auth/login` and `POST /auth/register` return a token, which the API
client stores before the route pushes on to the dashboard.

The **System** section probes nine subsystems live and reports what actually
came back — status, latency, and the database component from `/health`. A 401
or 403 counts as reachable, because the question it answers is whether the
backend is connected, not whether you are an admin.

The **Learning Universe** is the signature view: the learner's skill graph as
an explorable 3D galaxy. It is a second projection of the same `GraphModel`
the 2D knowledge graph renders — one source of truth, two views. Prerequisite
rank becomes altitude (foundations at the bottom, the goal overhead, so
learning literally reads as ascending), each rank's skills sit on a ring
ordered by the same barycentre pass as the 2D layout, and mastery is the
visual language: mastered skills burn green, learning amber, weak red, and
everything the learner has not started sits dim and translucent in the
*knowledge fog*, waiting to be discovered. Goal skills are ringed landmarks.
Selecting a star lights its full prerequisite route, eases the camera to it,
and opens the same grounded detail panel as the 2D view.

The AI mentor drives the universe: every coach reply is broadcast, and when it
names a skill that exists in the galaxy, that star is selected and pulsed — so
"can I ask how comfortable you are with Linear Algebra?" physically points at
Linear Algebra. The 3D layer is a projection of the underlying engines, not a
decoration: nothing appears in the galaxy that the graph and profile data did
not put there. WebGL loads lazily (`next/dynamic`, no SSR), so the three.js
bundle stays out of the first paint.

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

## Known limits

Everything in the original brief is implemented. What remains is scope, not
absence:

**General questions need a configured model.** Prerequisite questions ("why do
I need linear algebra for machine learning?") are answered deterministically
from the graph and always work. Open subject-matter questions ("CNNs vs
transformers?") are routed to `_answer_general`, which is the one place the
model supplies facts rather than prose — with `LLM_PROVIDER=mock` it declines
and points at the catalogue instead of guessing.

**Reviewer grading does not re-run the adaptive engine.** Marking a short
answer correct re-scores the attempt, but does not replay the proficiency
update or milestone unlock that the original submission triggered.

**Declared courses only suppress on an exact match** — an explicit
`resource_id`, an equal URL, or an unambiguous title. Fuzzy matching is
deliberately absent: hiding a resource the learner never took is a worse
failure than showing one they did.

**Feedback reaches ranking per-provider only.** `_provider_success` turns the
learner's own resource feedback into a prior feeding the `historical_success`
feature; it is not per-resource, per-modality or per-topic.

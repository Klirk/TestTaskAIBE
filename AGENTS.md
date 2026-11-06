# AGENTS.md — AI-First Helpdesk Backend Assistant

> Project-level directives, architectural contracts, and coding guidelines for AI coding agents (OpenCode, Claude Code, Cursor, Codex) working on this repository.

---

## 1. Project Overview & Business Domain

The service automates customer support ticket processing by generating draft responses using an LLM and an internal Knowledge Base (RAG), supervised by human operators (Human-in-the-Loop moderation).

### Key Functional & Non-Functional Requirements:

1. **Webhook Ingestion (`POST /webhooks/helpdesk`)**:
   - **Response SLA**: **Strictly < 2 seconds** (target: < 50ms). If the webhook does not respond within 2 seconds, the helpdesk retries delivery.
   - **Peak Throughput**: Normal load is a few requests per minute; peak load is up to **500 requests per 10 minutes**. Zero tickets may be lost.
   - **Deduplication / Idempotency**: Identical events (`event_id`) and duplicate tickets (`ticket_id`) can arrive multiple times, including simultaneously in parallel requests.
   - **Exact Webhook Request Payload**:
     ```json
     {
       "event_id": "evt_8f2a",
       "ticket_id": "T-1042",
       "customer_email": "user@example.com",
       "message": "Не можу експортувати звіт у PDF",
       "reply_url": "https://helpdesk.example.com/tickets/T-1042/replies"
     }
     ```

2. **LLM & Knowledge Base (RAG)**:
   - **Knowledge Base**: 5–10 short articles about a fictional SaaS product stored in PostgreSQL and seeded automatically on startup.
   - **Draft Generation**: Finds relevant KB articles and generates a draft response containing links/references to those articles.
   - **Latency Profile**: Each LLM call takes **5–30 seconds**.
   - **Global Rate Limit**: Strictly **60 requests per minute (RPM)** across the entire service.
   - **Concurrency Requirement**: Because a single LLM call takes 5–30s, a sequential worker would only process 2–12 tickets/min. To handle 500 tickets per 10 minutes (50/min) within the 60 RPM ceiling, background processing **must run concurrently** (e.g., `asyncio.Semaphore(25)` combined with an async 60 RPM sliding-window / token-bucket limiter).
   - **No-API-Key Mode (Mandatory Requirement)**: The service must work without an API key. Even without an API key, it **must still make a real HTTP request to the LLM provider** (handling the expected 401/403 error), wait for a simulated latency of **5–30 seconds** (`asyncio.sleep(random.uniform(5.0, 30.0))`), and return a static fallback draft referencing the matched KB articles. The rest of the pipeline treats this response identically to a live LLM response.

3. **Human Moderation Interface**:
   - Minimal web interface (FastAPI + Jinja2 + HTMX) where operators view the list of tickets with their generated drafts and can **Approve** or **Reject** them.

4. **Client Dispatch (`POST <reply_url>`)**:
   - Triggered **only** after operator approval.
   - **Exact Outgoing Payload**:
     ```json
     {
       "ticket_id": "T-1042",
       "message": "Щоб експортувати звіт у PDF, відкрийте..."
     }
     ```
   - **Expected Success Status**: `201 Created`.
   - **Failure Modes & Strict At-Most-Once Delivery**: The helpdesk occasionally returns `5xx` or times out. **The customer must never receive the same reply twice.** Use atomic state locking (`SELECT ... FOR UPDATE`), an `Idempotency-Key` header (`Idempotency-Key: <ticket_id>`), and idempotent state checks on the mock helpdesk.

5. **Helpdesk Mock**:
   - Built-in mock helpdesk endpoints (e.g. `POST /mock/helpdesk/tickets/{ticket_id}/replies` and a load/webhook trigger utility) that simulate `201 Created`, intermittent `5xx` errors, network timeouts, and duplicate webhook deliveries.

---

## 2. Tech Stack & Environment

- **Runtime**: Python 3.14 (100% `asyncio`, native type unions, zero blocking calls)
- **Web Framework**: FastAPI (async routes, `lifespan` context manager for worker pool & DB seeding)
- **Database**: PostgreSQL 18 (`asyncpg` driver)
- **ORM & Migrations**: SQLAlchemy 2.0 (`AsyncSession`, 2.0 `select()` syntax) + Alembic
- **Background Processing**: Asyncio worker pool polling PostgreSQL via `SELECT ... FOR UPDATE SKIP LOCKED` (or Redis + ARQ), started automatically inside FastAPI lifespan or as a compose worker service
- **HTTP Client**: `httpx.AsyncClient` (shared client with connection pooling and explicit timeouts)
- **Validation**: Pydantic v2 & `pydantic-settings`
- **Frontend**: Jinja2 + HTMX (server-rendered, zero Node.js build step)
- **Deployment**: `docker compose up --build`

---

## 3. Core Architecture & Async Execution Flow

```text
                      1. POST /webhooks/helpdesk (< 50ms)
[Helpdesk System] ──────────────────────────────────────────► [FastAPI Ingestion]
       ▲                                                             │
       │                                                             │ 2. Atomic UPSERT (ON CONFLICT DO NOTHING)
       │                                                             ▼
       │                                                    [(PostgreSQL) Tickets & Events]
       │                                                             │
       │                                                             │ 3. Concurrent Async Worker Pool
       │                                                             ▼
       │                                                    [Async Background Workers]
       │                                                             │
       │                                                             ├─► Global Rate Limiter (60 RPM)
       │                                                             ├─► Retrieve KB Articles (RAG)
       │                                                             └─► LLM Call + No-Key Fallback (5-30s)
       │                                                             │
       │                                                             ▼
       │                                                    [Status: READY_FOR_REVIEW]
       │                                                             │
       │                                                             ▼
       │ 5. POST <reply_url> (201 Created, Idempotent)      [Operator Moderation UI]
       └─────────────────────────────────────────────────── (Approve / Reject via HTMX)
```

### 3.1. Webhook Ingestion & Deduplication
- Maintain an `webhook_events` table (or `event_id` unique constraint) and `tickets` table (`ticket_id` unique constraint).
- Use PostgreSQL `INSERT ... ON CONFLICT (event_id) DO NOTHING` and `ON CONFLICT (ticket_id) DO NOTHING` so concurrent duplicate webhook calls never raise unhandled `IntegrityError` and never create duplicate jobs.
- Return `200 OK` / `202 Accepted` immediately (< 50ms) without waiting for RAG or LLM.

### 3.2. Rate Limiting (60 RPM) & No-Key Fallback LLM Client
- Implement an async sliding-window or token-bucket rate limiter capped at **60 requests per 60 seconds**.
- In `LLMService.generate_draft(ticket, articles)`:
  1. Acquire a slot from the 60 RPM rate limiter.
  2. Always issue an async HTTP request via `httpx.AsyncClient` to the configured LLM provider URL (even when `LLM_API_KEY` is unset/empty).
  3. If `LLM_API_KEY` is missing or the provider returns `401/403` in fallback mode:
     - Measure elapsed time and `await asyncio.sleep(...)` so total call duration is between **5.0 and 30.0 seconds**.
     - Return a structured draft response in Ukrainian citing the matched KB articles (including their titles and URLs).

### 3.3. Operator Moderation & Duplicate Prevention
- Ticket state machine:
  `NEW` ➔ `GENERATING_DRAFT` ➔ `READY_FOR_REVIEW` ➔ `SENDING` ➔ `SENT` (or `REJECTED` / `DELIVERY_FAILED`).
- When an operator clicks **Approve**:
  - Lock the ticket row atomically:
    ```sql
    SELECT * FROM tickets WHERE id = :id AND status = 'READY_FOR_REVIEW' FOR UPDATE SKIP LOCKED;
    ```
  - Transition status to `SENDING` and commit before making the external HTTP request.
  - Dispatch `POST <reply_url>` with JSON `{"ticket_id": ticket.ticket_id, "message": ticket.draft_reply}` and header `Idempotency-Key: <ticket_id>`.
  - On `201 Created`, update status to `SENT`.
  - On `5xx` or timeout, retry with exponential backoff using the same `Idempotency-Key`. The mock helpdesk (and real idempotent receivers) must deduplicate by `ticket_id` / `Idempotency-Key` so a retry after a timeout never produces a duplicate message to the end user.

---

## 4. Code Standards & Async Rules

1. **100% Asynchronous Non-Blocking Execution**:
   - **FORBIDDEN**: `requests`, `urllib.request`, `time.sleep`, `psycopg2`, or synchronous file/network I/O inside async functions.
   - **REQUIRED**: `httpx.AsyncClient`, `asyncio.sleep`, `asyncpg`, `AsyncSession`.

2. **Database Access**:
   - SQLAlchemy 2.0 syntax only (`select()`, `insert().on_conflict_do_nothing()`).
   - Always manage sessions via `async with async_session_maker() as session:`.

3. **Modern Python 3.14 Conventions**:
   - Use native union types (`str | None`), built-in generic types (`list[str]`, `dict[str, Any]`), and `typing.Annotated` for FastAPI dependencies.

4. **Zero Comments Policy**:
   - Never write docstrings (`"""..."""`), inline comments (`# ...`), or HTML comments (`<!-- ... -->`) in code or configuration files.

5. **Git Commit Discipline (Strict Submission Requirement)**:
   - The evaluation requires the **raw Git commit history ("as is", NO squash)**.
   - Make logical, incremental commits after completing each milestone (e.g., `feat: initial project setup and docker compose`, `feat: add async db models and webhook deduplication`, `feat: implement RAG and 60rpm LLM service with no-key fallback`, `feat: add HTMX moderation UI and idempotent reply delivery`, `test: add async test suite`).
   - **NEVER** run `git rebase -i`, `git merge --squash`, or `git reset --soft` to squash history.

---

## 5. Repository Structure

```text
.
├── docker-compose.yml          # Starts app, postgres, and runs migrations/seeding automatically
├── Dockerfile                  # Python 3.14-slim image
├── pyproject.toml              # Project dependencies (fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, httpx, etc.)
├── README.md                   # Detailed setup instructions, architecture overview, and demo usage
├── AGENTS.md                   # Agent specification and architectural rules
├── CLAUDE.md                   # Reference pointer to AGENTS.md
├── alembic.ini
├── alembic/                    # Async Alembic migrations
├── src/
│   ├── main.py                 # FastAPI app, lifespan (DB init, KB seed, worker startup)
│   ├── config.py               # Pydantic BaseSettings
│   ├── database.py             # async_engine, async_sessionmaker, Base
│   ├── models.py               # SQLAlchemy models: Ticket, WebhookEvent, KnowledgeArticle
│   ├── schemas.py              # Pydantic v2 schemas matching exact spec payloads
│   ├── api/
│   │   ├── webhooks.py         # POST /webhooks/helpdesk (<2s SLA, idempotent)
│   │   ├── moderation.py       # GET /, POST /tickets/{id}/approve, POST /tickets/{id}/reject
│   │   └── mock_helpdesk.py    # POST /mock-helpdesk/tickets/{ticket_id}/replies (201, 5xx simulation)
│   ├── services/
│   │   ├── rate_limiter.py     # Async 60 RPM rate limiter
│   │   ├── llm_service.py      # Real provider call + 5-30s fallback mode
│   │   ├── rag_service.py      # KB article search & ranking
│   │   └── delivery_service.py # Idempotent reply sender with retry handling
│   ├── worker/
│   │   └── processor.py        # Concurrent async background worker pool
│   ├── knowledge_base/
│   │   └── articles.json       # 5-10 fictional product KB articles
│   └── templates/
│       ├── index.html          # Operator dashboard (Jinja2 + HTMX)
│       └── partials/           # HTMX ticket row/card partials
└── tests/
    ├── conftest.py             # Async fixtures
    ├── test_webhooks.py        # SLA <2s, concurrent duplicate event_id tests
    ├── test_llm_and_rag.py     # 60 RPM rate limit & no-key real-request fallback tests
    └── test_delivery.py        # 5xx retry & strict at-most-once delivery tests
```

---

## 6. Common Commands

```bash
# Start the entire service stack (single command requirement)
docker compose up --build

# Run test suite
pytest -v --asyncio-mode=auto

# Lint & typecheck
ruff check . && ruff format --check .
```

---

## 7. Critical Invariants for Agents (Checklist before finishing)

1. **Webhook latency < 2s**: `POST /webhooks/helpdesk` only persists the event/ticket and enqueues work; it never waits for the 5–30s LLM call.
2. **Simultaneous duplicates**: Sending 10 parallel requests with the same `event_id` or `ticket_id` must result in exactly 1 ticket and 0 HTTP 500 errors.
3. **No-API-Key behavior**: With no API key set, the app still performs an outgoing HTTP request to the LLM provider URL, waits 5–30s total, and returns a realistic draft with KB links.
4. **60 RPM cap**: Under a 500-ticket burst, outgoing LLM calls never exceed 60 requests per rolling minute, while multiple calls wait/execute concurrently in flight.
5. **No double replies**: Even if `reply_url` returns `500`/`502` or times out on the first attempt, the customer never receives duplicate messages.

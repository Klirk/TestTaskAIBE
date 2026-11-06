# AI-First Helpdesk Backend Assistant

Асинхронний бекенд-сервіс для автоматичної підготовки чернеток відповідей служби підтримки за допомогою LLM та бази знань (RAG) із вебінтерфейсом модерації оператора та захистом від дублікатів.

## Стек технологій

- **Python 3.14** (`asyncio`)
- **FastAPI** + **Jinja2 / HTMX** (вебінтерфейс модератора)
- **PostgreSQL 18** (`asyncpg` + **SQLAlchemy 2.0 Async** + **Alembic**)
- **Celery + RabbitMQ 4** (фонова черга задач із пулом воркерів)
- **HTTPX** (`AsyncClient` для викликів LLM та відправки відповідей у Helpdesk)
- **Docker & Docker Compose**

## Архітектура та структура проєкту

```text
.
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── .env.example
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 0001_initial_schema.py
├── src/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── dependencies.py
│   │   ├── exceptions.py
│   │   └── lifespan.py
│   ├── models/
│   │   ├── base.py
│   │   ├── ticket.py
│   │   ├── webhook_event.py
│   │   ├── knowledge_article.py
│   │   └── mock_reply.py
│   ├── schemas/
│   │   ├── ticket.py
│   │   ├── webhook.py
│   │   └── knowledge.py
│   ├── repositories/
│   │   ├── ticket_repository.py
│   │   ├── webhook_repository.py
│   │   ├── knowledge_repository.py
│   │   └── mock_reply_repository.py
│   ├── services/
│   │   ├── rate_limiter.py
│   │   ├── rag_service.py
│   │   ├── llm_service.py
│   │   ├── ticket_service.py
│   │   └── delivery_service.py
│   ├── workers/
│   │   ├── celery_app.py
│   │   ├── tasks.py
│   │   └── ticket_processor.py
│   ├── api/
│   │   ├── router.py
│   │   ├── v1/
│   │   │   ├── webhooks.py
│   │   │   └── mock_helpdesk.py
│   │   └── web/
│   │       └── moderation.py
│   └── templates/
│       ├── index.html
│       └── partials/
│           └── ticket_row.html
└── tests/
    ├── conftest.py
    ├── test_webhooks.py
    ├── test_llm_and_rag.py
    └── test_delivery.py
```

## Запуск через Docker Compose

1. Запустіть сервіс та базу даних PostgreSQL 18 однією командою:
   ```bash
   docker compose up --build
   ```
2. Після запуску доступні:
   - **Вебінтерфейс оператора**: `http://localhost:8000/`
   - **Вебхук хелпдеску**: `POST http://localhost:8000/webhooks/helpdesk`
   - **Мок хелпдеску (прийом відповідей)**: `POST http://localhost:8000/mock/helpdesk/tickets/{ticket_id}/replies`
   - **Swagger / OpenAPI**: `http://localhost:8000/docs`

## Перевірка роботи вебхука

```bash
curl -X POST http://localhost:8000/webhooks/helpdesk \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_8f2a",
    "ticket_id": "T-1042",
    "customer_email": "user@example.com",
    "message": "Не можу експортувати звіт у PDF",
    "reply_url": "https://helpdesk.example.com/tickets/T-1042/replies"
  }'
```

## Локальний запуск та тестування

```bash
docker compose up -d db
alembic upgrade head
pytest -v
ruff check .
uvicorn src.main:app --reload --port 8000
```

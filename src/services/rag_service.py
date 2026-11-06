import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.knowledge_article import KnowledgeArticle
from src.repositories.knowledge_repository import KnowledgeRepository

_WORD_RE = re.compile(r"[\wіїєґІЇЄҐ0-9]{2,}", re.UNICODE)

DEFAULT_ARTICLES: list[dict[str, Any]] = [
    {
        "slug": "pdf-export-guide",
        "title": "Експорт звітів у формат PDF та вирішення помилок генерації",
        "url": "https://docs.cloudflow.example.com/uk/reports/pdf-export",
        "content": (
            "Щоб експортувати звіт у PDF, відкрийте потрібний дашборд у розділі «Аналітика», "
            "натисніть кнопку «Експорт» у верхньому правому куті та оберіть формат «PDF (A4)». "
            "Якщо кнопка неактивна або виникає помилка завантаження, вимкніть блокувальник "
            "спливаючих вікон у браузері та переконайтеся, що у звіті обрано період "
            "не більше 365 днів."
        ),
        "keywords": [
            "експорт",
            "експортувати",
            "звіт",
            "звіти",
            "pdf",
            "пдф",
            "скачати",
            "завантажити",
            "друк",
        ],
    },
    {
        "slug": "billing-and-invoices",
        "title": "Керування підпискою, оплата карткою та завантаження рахунків-фактур",
        "url": "https://docs.cloudflow.example.com/uk/billing/subscriptions-and-invoices",
        "content": (
            "Для зміни тарифного плану або оновлення платіжної картки перейдіть у "
            "«Налаштування» -> «Білінг та підписка». Усі закриті рахунки-фактури (інвойси) "
            "та акти виконаних робіт доступні для завантаження у вкладці «Історія платежів». "
            "При помилці списання перевірте ліміт інтернет-оплат у банкінгу."
        ),
        "keywords": [
            "оплата",
            "рахунок",
            "інвойс",
            "тариф",
            "підписка",
            "картка",
            "білінг",
            "гроші",
            "списання",
        ],
    },
    {
        "slug": "two-factor-authentication",
        "title": "Налаштування двофакторної автентифікації (2FA) та відновлення доступу",
        "url": "https://docs.cloudflow.example.com/uk/security/2fa-setup",
        "content": (
            "Щоб увімкнути або скинути двофакторну автентифікацію (2FA), відкрийте "
            "«Профіль» -> «Безпека» та відскануйте QR-код у додатку Google Authenticator "
            "або Authy. "
            "Якщо ви втратили доступ до пристрою 2FA, скористайтеся одним із резервних кодів "
            "відновлення або зверніться до адміністратора вашого воркспейсу."
        ),
        "keywords": [
            "2fa",
            "пароль",
            "вхід",
            "увійти",
            "автентифікація",
            "код",
            "безпека",
            "логін",
            "доступ",
        ],
    },
    {
        "slug": "api-keys-and-webhooks",
        "title": "Генерація API-ключів та налаштування вихідних вебхуків",
        "url": "https://docs.cloudflow.example.com/uk/developers/api-and-webhooks",
        "content": (
            "Створити новий API-ключ можна у розділі «Налаштування» -> «API та інтеграції». "
            "Зверніть увагу, що секретний токен відображається лише один раз під час створення. "
            "Ліміт запитів до REST API становить 120 запитів на хвилину. Для перевірки підпису "
            "вебхуків використовуйте заголовок X-CloudFlow-Signature."
        ),
        "keywords": [
            "api",
            "ключ",
            "токен",
            "вебхук",
            "webhook",
            "інтеграція",
            "401",
            "429",
            "розробник",
        ],
    },
    {
        "slug": "team-roles-and-permissions",
        "title": "Запрошення колег та розподіл ролей у команді",
        "url": "https://docs.cloudflow.example.com/uk/workspace/team-permissions",
        "content": (
            "Щоб запросити нового учасника, перейдіть у «Команда» -> «Учасники» та натисніть "
            "«Запросити за email». Доступні ролі: Власник (повний доступ і білінг), "
            "Адміністратор (керування користувачами та звітами), Редактор (створення дашбордів) "
            "та Спостерігач (лише перегляд та експорт)."
        ),
        "keywords": [
            "команда",
            "роль",
            "права",
            "доступ",
            "запрошення",
            "колега",
            "користувач",
            "адміністратор",
        ],
    },
    {
        "slug": "csv-excel-data-import",
        "title": "Імпорт даних із файлів CSV та Excel (XLSX)",
        "url": "https://docs.cloudflow.example.com/uk/data/csv-excel-import",
        "content": (
            "Для завантаження власних таблиць відкрийте «Джерела даних» -> «Імпорт файлу». "
            "Підтримуються формати CSV (кодування UTF-8, роздільник кома або крапка з комою) "
            "та XLSX розміром до 100 МБ. Переконайтеся, що перший рядок таблиці містить назви "
            "колонок, а дати записані у форматі YYYY-MM-DD."
        ),
        "keywords": [
            "імпорт",
            "csv",
            "excel",
            "xlsx",
            "таблиця",
            "файл",
            "кодування",
            "utf-8",
            "завантажити",
        ],
    },
    {
        "slug": "dashboard-slow-loading",
        "title": "Оптимізація швидкодії дашбордів та кешування запитів",
        "url": "https://docs.cloudflow.example.com/uk/reports/performance-optimization",
        "content": (
            "Якщо дашборд завантажується повільно, зменшіть кількість віджетів на одній сторінці "
            "(рекомендовано до 12) або увімкніть автоматичне кешування у параметрах джерела даних. "
            "Для великих вибірок використовуйте агреговані таблиці та фільтр за датою."
        ),
        "keywords": [
            "повільно",
            "гальмує",
            "довго",
            "дашборд",
            "кеш",
            "швидкість",
            "помилка",
            "зависає",
        ],
    },
    {
        "slug": "notifications-slack-telegram",
        "title": "Налаштування сповіщень у Slack, Telegram та на Email",
        "url": "https://docs.cloudflow.example.com/uk/integrations/alerts-and-notifications",
        "content": (
            "Щоб отримувати автоматичні звіти або алерти про аномалії, перейдіть у "
            "«Сповіщення» -> «Канали доставки». Підключіть офіційний бот CloudFlow у Telegram "
            "або авторизуйте робочий простір Slack. Ви можете налаштувати розклад відправки "
            "щодня або щопонеділка о 09:00."
        ),
        "keywords": [
            "сповіщення",
            "алерт",
            "slack",
            "telegram",
            "телеграм",
            "лист",
            "email",
            "бот",
            "розсилка",
        ],
    },
]


class RAGService:
    @staticmethod
    async def seed_knowledge_base(session: AsyncSession) -> None:
        repo = KnowledgeRepository(session)
        await repo.upsert_articles(DEFAULT_ARTICLES)
        await session.commit()

    async def find_relevant_articles(
        self,
        session: AsyncSession,
        query_text: str,
        top_k: int = 2,
    ) -> list[KnowledgeArticle]:
        repo = KnowledgeRepository(session)
        all_articles = await repo.list_all()
        if not all_articles:
            return []

        query_lower = query_text.lower()
        query_tokens = set(_WORD_RE.findall(query_lower))

        scored: list[tuple[float, int, KnowledgeArticle]] = []
        for idx, article in enumerate(all_articles):
            score = self._score_article(query_lower, query_tokens, article)
            scored.append((score, -idx, article))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        matched = [item[2] for item in scored if item[0] > 0][:top_k]

        if not matched:
            return all_articles[: min(top_k, len(all_articles))]
        return matched

    @staticmethod
    def _score_article(
        query_lower: str,
        query_tokens: set[str],
        article: KnowledgeArticle,
    ) -> float:
        score = 0.0
        for kw in article.keywords:
            kw_lower = kw.lower()
            if kw_lower in query_lower:
                score += 4.0
            else:
                for token in query_tokens:
                    if len(token) >= 3 and (
                        token.startswith(kw_lower[:4]) or kw_lower.startswith(token[:4])
                    ):
                        score += 2.0

        title_tokens = set(_WORD_RE.findall(article.title.lower()))
        content_tokens = set(_WORD_RE.findall(article.content.lower()))

        for token in query_tokens:
            if token in title_tokens:
                score += 2.5
            if token in content_tokens:
                score += 1.0
            if len(token) >= 4:
                prefix = token[:4]
                if any(t.startswith(prefix) for t in title_tokens):
                    score += 1.5
                if any(t.startswith(prefix) for t in content_tokens):
                    score += 0.5

        return score

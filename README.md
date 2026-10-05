# job-aggregator

`job-aggregator` — backend-сервис для агрегации вакансий разработчиков с HH.ru.

Сервис собирает вакансии из внешних источников, сохраняет их в PostgreSQL без
дубликатов, обновляет уже известные вакансии и предоставляет данные через
REST API.

## MVP

В рамках MVP проект должен уметь:

- запускать FastAPI-приложение;
- подключаться к PostgreSQL через настройки окружения;
- собирать вакансии разработчиков с HH.ru;
- сохранять вакансии через SQLAlchemy 2.x;
- предотвращать дубли по внешнему идентификатору вакансии;
- обновлять изменившиеся данные уже сохранённых вакансий;
- отдавать сохранённые вакансии через REST API;
- поддерживать фильтрацию и пагинацию;
- запускать сбор вручную для демонстрации и по расписанию;
- покрывать основную логику тестами без реальных сетевых запросов.

Не входит в MVP, если не останется времени: автоотклики, уведомления,
AI-фильтрация, статистика рынка и административный интерфейс.

## Стек

- Python 3.14
- FastAPI
- PostgreSQL
- SQLAlchemy 2.x
- aiohttp / asyncio
- APScheduler
- pytest
- uv


## Целевая структура проекта

Сейчас в репозитории находится минимальный каркас. По мере выполнения задач
YouTrack он вырастет до следующей структуры:

```text
job-aggregator/
├── alembic/                         # миграции PostgreSQL
│   ├── env.py
│   └── versions/
├── alembic.ini
├── docker-compose.yml                # локальная PostgreSQL
├── docs/                             # карта реализации и документация команды
├── src/job_aggregator/
│   ├── api/                          # HTTP-роуты FastAPI
│   │   ├── health.py
│   │   ├── hh_auth.py                # OAuth-endpoint-ы HH.ru
│   │   ├── collection.py             # ручной запуск сбора
│   │   ├── saved_searches.py
│   │   ├── vacancies.py
│   │   └── router.py                 # подключение роутеров
│   ├── core/
│   │   ├── config.py                 # Settings из environment variables
│   │   └── logging.py
│   ├── db/
│   │   ├── base.py                   # Base и TimestampMixin
│   │   ├── session.py                # engine и AsyncSession
│   │   ├── models/
│   │   │   ├── vacancy.py
│   │   │   ├── saved_search.py
│   │   │   └── hh_account_token.py
│   │   └── repositories/
│   │       ├── vacancies.py
│   │       └── saved_searches.py
│   ├── integrations/
│   │   └── hh/
│   │       ├── dto.py                # данные поиска и вакансий HH.ru
│   │       ├── client.py             # низкоуровневый клиент HH.ru
│   │       ├── oauth.py
│   │       ├── provider.py           # real-провайдер вакансий
│   │       ├── fake_provider.py      # данные для тестов и разработки
│   │       ├── mapper.py
│   │       ├── factory.py
│   │       └── errors.py
│   ├── schemas/                      # request/response DTO REST API
│   │   ├── vacancy.py
│   │   ├── collection.py
│   │   └── saved_search.py
│   ├── services/
│   │   ├── collection.py             # бизнес-логика сбора
│   │   └── tokens.py
│   ├── scheduler/
│   │   └── scheduler.py
│   └── main.py                       # создание FastAPI-приложения
└── tests/
    ├── api/
    ├── db/
    ├── integrations/hh/
    └── services/
```

Не все каталоги нужно создавать заранее: они появляются только вместе с
соответствующей задачей. Это уменьшает пустые файлы и конфликты при merge.

Подробная карта этапов находится в
[docs/implementation-roadmap.md](docs/implementation-roadmap.md).


## Архитектура

Проект строится как простое слоистое приложение:

```text
HTTP-роуты FastAPI
  -> сервисы приложения
    -> репозитории и PostgreSQL
    -> интеграция с HH.ru
  -> response schemas

планировщик
  -> сервисы приложения
```

Основные зоны ответственности:

- `api` — HTTP-роуты FastAPI;
- `core` — конфигурация и логирование;
- `db` — подключение к базе данных, сессии SQLAlchemy и базовая metadata;
- `integrations` — клиенты внешних API;
- `services` — бизнес-логика приложения.
- `schemas` — публичные request/response-модели API;
- `scheduler` — запуск сервисов по расписанию.

Бизнес-логику не стоит размещать прямо в роутерах, если она становится
нетривиальной. Интеграции с внешними API должны быть изолированы от API-слоя и
тестироваться с моками.

`repositories` содержат только операции с PostgreSQL для конкретных сущностей;
общий generic repository не используется. `services` не зависят от FastAPI и
могут тестироваться с fake-провайдерами HH.ru без сети.

## Локальный запуск

```bash
uv sync
cp .env.example .env
uv run uvicorn job_aggregator.main:app --reload
```

Для локального запуска нужен PostgreSQL, доступный по `DATABASE_URL` из `.env`.

Проверка работоспособности приложения:

```bash
curl http://127.0.0.1:8000/health
```

Ожидаемый ответ:

```json
{"status": "ok"}
```

## Настройки окружения

Пример настроек находится в `.env.example`.

Основные переменные:

- `APP_NAME` — имя приложения;
- `APP_ENV` — окружение запуска;
- `LOG_LEVEL` — уровень логирования;
- `DATABASE_URL` — строка подключения к PostgreSQL.

Реальные секреты, токены и пароли нельзя коммитить в репозиторий.

## Тесты

```bash
uv run pytest
```

Тесты внешних интеграций должны использовать моки. Тестовый прогон не должен
зависеть от доступности реальных внешних API.

## Проверки перед Pull Request

После выполнения [JA-55 — Добавить Ruff для проверки и форматирования кода](https://StackEight.youtrack.cloud/issue/JA-55)
перед передачей изменений на ревью запускайте:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

`ruff check` находит базовые ошибки и неиспользуемые импорты, а
`ruff format --check` проверяет единый формат файлов. Если форматирование
требует изменений, выполните `uv run ruff format .` и добавьте результат в
свой коммит.

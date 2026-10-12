# Интеграция Job Aggregator с `hh-applicant-tool`

Этот документ фиксирует границу ответственности между Job Aggregator и
`hh-applicant-tool`.

Официальный контракт API HH.ru: <https://api.hh.ru/openapi/redoc>.

## Роль библиотеки

Приложение использует библиотеку только как низкоуровневый клиент HH.ru и
OAuth-helper. Используются публичные классы:

```python
from hh_applicant_tool.api import ApiClient, OAuthClient
```

Не используются `HHApplicantTool`, CLI-операции, собственный storage библиотеки,
UI, автоотклики, работа с резюме и другие высокоуровневые сценарии.

Зависимость подключена из PyPI как `hh-applicant-tool==2.0.1`. Пакет публикует
проект [`s3rgeym/hh-applicant-tool`](https://github.com/s3rgeym/hh-applicant-tool).
`uv.lock` фиксирует дистрибутив и его хеши, поэтому `uv sync` воспроизводимо
устанавливает проверенную версию.

```text
CollectionService
    → HHClient
        → компонент авторизованных запросов
            → ApiClient / OAuthClient из hh-applicant-tool
                → HH.ru API
```

Сервисы, API и репозитории не импортируют типы `hh_applicant_tool`. Клиент
преобразует raw-ответ библиотеки во внутренние DTO проекта.

В MVP источник вакансий один — HH.ru. Поэтому отдельный runtime-контракт
`HHVacancyProvider`, fake-реализация и выбор fake/real по переменной окружения
не используются. `HHClient` — единый фасад интеграции HH.ru: сейчас он
предоставляет поиск вакансий, а новые методы API добавляются в него по мере
необходимости. `CollectionService` получает рабочий `HHClient` через
dependency приложения. В тестах зависимость подменяется mock, stub или
`FakeHHClient` с нужным поведением; тестовая реализация не входит в
production-код.

## Вызов API и дополнительные endpoint-ы

`ApiClient` предоставляет универсальный метод `request()` и методы `get()`,
`post()`, `put()`, `delete()`. Поэтому нужный endpoint HH.ru вызывается нашим
адаптером через клиент библиотеки, а не через CLI.

```text
HHClient → ApiClient.get("/vacancies", params=...) → raw JSON
    → VacancyData и HHVacancyPage → CollectionService
```

Добавление нового endpoint-а не должно менять сервисы сбора или API-слой. Весь
код обращения к HH.ru остаётся в `job_aggregator.integrations.hh`.

## Токены и OAuth

Все реальные запросы к HH.ru выполняются от имени авторизованного пользователя.
Приложение хранит `access_token`, `refresh_token` и время истечения в собственной
PostgreSQL-модели `HHAccountToken`. Токены не передаются через публичный REST API
и не выводятся в логи.

При запросе приложение:

1. читает токены из PostgreSQL через собственный `TokenService`;
2. создаёт `ApiClient` с этими значениями;
3. выполняет запрос;
4. сохраняет обратно изменившиеся токены.

```text
PostgreSQL → TokenService → ApiClient → HH.ru
                                  ↓
                         get_access_token()
                                  ↓
                             PostgreSQL
```

Встроенные OAuth client settings `hh-applicant-tool` допускается использовать
как принятое командой техническое решение. Хранение токенов всё равно остаётся
ответственностью Job Aggregator.

## Автоматическое обновление токена

Нужно использовать `ApiClient.request()` или его методы `get()` / `post()`, а
не вызывать `BaseClient.request()` напрямую. `ApiClient` при `Forbidden` и
истёкшем access token пытается обновить токен и повторяет исходный запрос.

Обновлённые значения существуют только в памяти `ApiClient`. После каждого
запроса наш адаптер получает их через `get_access_token()` и сохраняет через
`TokenService`, в том числе если повторный запрос завершился ошибкой.

```python
try:
    result = await asyncio.to_thread(
        api_client.get,
        "/vacancies",
        params=params,
    )
finally:
    await token_service.save_if_changed(api_client.get_access_token())
```

## Async, конкуренция и логи

`hh-applicant-tool` использует синхронный `requests`. Из async-кода приложения
его методы вызываются через `asyncio.to_thread`, чтобы не блокировать event loop
FastAPI.

Refresh token HH.ru может быть одноразовым. Для одного набора токенов нельзя
одновременно запускать несколько операций обновления: `TokenService` или
адаптер должен синхронизировать refresh простым lock.

Библиотека может логировать параметры запросов на DEBUG-уровне. Логгер
`hh_applicant_tool` не должен выводить DEBUG-сообщения в окружениях, где в
параметрах могут быть OAuth code, access token или refresh token.

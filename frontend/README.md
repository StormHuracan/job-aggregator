# Frontend Job Aggregator

Vue 3 + TypeScript + Vite. Зависимости устанавливаются через `npm ci`
из каталога `frontend/`.

## Локальный запуск

```bash
npm run dev -- --host 127.0.0.1
```

Vite доступен на `http://127.0.0.1:5173`. В `.env.example` задано
`VITE_API_BASE_URL=/api`. Без переменной используется то же значение.
Dev proxy направляет `/api/*` в FastAPI на `http://127.0.0.1:8000`, удаляя
префикс `/api`. Для production нужен аналогичный reverse proxy или заданный
при сборке `VITE_API_BASE_URL` и соответствующая настройка backend.

## API-контракты

`src/api/client.ts` отправляет cookie через `credentials: "include"`.
HTTP 401 сохраняет статус в `ApiError` для route guard; остальные HTTP и
сетевые ошибки имеют безопасные сообщения без тела ответа сервера.
Ответ 204 возвращает `undefined`; некорректный JSON успешного ответа отклоняется.
TypeScript-типы описывают контракт; runtime-валидация полей JSON не выполняется.

Модули:

- `user.ts`: `/me`, настройки, отметка прочитанных matches и logout (JA-67).
- `vacancies.ts`: фильтры и пагинация `/vacancies` (JA-39).
- `saved-searches.ts`: список, создание и изменение `is_enabled` (JA-38).
- `collection.ts`: inline-запуск сбора с `text`, `area`, `pages_limit` (JA-37).

Страница `/saved-searches` использует реальный backend API: загрузку списка,
создание и включение/выключение поисков. Для неё нужна действующая cookie-сессия;
при 401 открывается `/login`. Формы показывают безопасные ошибки валидации 422.
OAuth-вход и `/me` ещё ожидают реализации: текущий router и личный кабинет
используют demo fixture, вакансии — локальные данные.

Токены и session cookie приложение не читает, не сохраняет в web storage
и не выводит в console. OAuth session cookie управляет backend.

## Проверки

```bash
npm test
npm run typecheck
npm run build
```

API-тесты подменяют только `fetch` и проверяют публичные функции адаптеров:
пути, методы, payload, cookie, сериализацию query-параметров и ошибки.

Component-тесты страницы поисков проходят через настоящий API-клиент с
подменой `fetch`: проверяют pending, 401, 422, повтор загрузки и изоляцию состояния.

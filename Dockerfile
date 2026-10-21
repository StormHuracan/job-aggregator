FROM ghcr.io/astral-sh/uv:0.12.5 AS uv
FROM python:3.14-slim

COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

COPY alembic.ini ./
COPY alembic ./alembic

USER 10001:10001
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn job_aggregator.main:app --host 0.0.0.0 --port 8000 --workers 1"]

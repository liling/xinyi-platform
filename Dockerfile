FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --extra dev --no-cache || uv sync --no-cache

COPY xinyi_platform ./xinyi_platform
COPY alembic.ini ./

EXPOSE 8000

CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn xinyi_platform.main:app --host 0.0.0.0 --port 8000"]

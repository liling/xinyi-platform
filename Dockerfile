FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        tzdata \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Shanghai

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --extra dev --no-cache || uv sync --no-cache

COPY xinyi_platform ./xinyi_platform
COPY alembic.ini ./
RUN uv pip install -e .

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8000

CMD ["uvicorn", "xinyi_platform.main:app", "--host", "0.0.0.0", "--port", "8000"]

# xinyi-platform

Identity and authentication platform for xinyi business services.

## Development

```bash
uv sync --extra dev
cp .env.example .env
uv run alembic upgrade head
uv run uvicorn xinyi_platform.main:app --reload --port 8000
```

## Tests

```bash
uv run pytest
```

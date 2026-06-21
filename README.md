# xinyi-platform

Identity and authentication platform for xinyi business services.

## Quick Start

```bash
# 1. Start Postgres
docker run -d --name xinyi-pg -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=hindsight \
  postgres:16

# 2. Configure
cp .env.example .env
# Edit .env — generate secrets:
#   python -c "import secrets; print(secrets.token_urlsafe(48))"  # JWT_SECRET
#   python -c "import secrets; print(secrets.token_hex(16))"     # ENCRYPTION_KEY

# 3. Install + migrate
uv sync --extra dev
uv run alembic upgrade head

# 4. Run
uv run uvicorn xinyi_platform.main:app --reload --port 8000
```

Open http://localhost:8000/login — log in with `admin` and `ADMIN_PASSWORD` from `.env`.

## Architecture

- **Postgres schema:** `xinyi` (8 tables: users, business_clients, oauth_codes, refresh_tokens, token_revocations, audit_logs, login_history, email_verifications)
- **Auth:** OAuth2 authorization code flow for business clients; local + CAS for user login
- **JWT:** HS256, 15min access TTL, 7d refresh TTL, business clients verify locally with shared `jwt_secret`
- **Internal API:** server-to-server, authenticated via `X-Client-Id` + `X-Client-Secret`

## Development

```bash
uv run pytest                    # all tests
uv run pytest tests/unit/ -v     # unit tests only
uv run pytest tests/api/ -v      # API tests only
```

See `docs/local-smoke-test.md` for end-to-end manual verification.

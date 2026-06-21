# Local Smoke Test

End-to-end manual verification for xinyi-platform.

## Prerequisites

- Docker (for Postgres)
- uv (Python dependency management)

## Setup

```bash
# Start Postgres
docker run -d --name xinyi-pg -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=hindsight \
  postgres:16

# Configure
cp .env.example .env
# Edit .env:
#   XINYI_PLATFORM_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/hindsight
#   XINYI_PLATFORM_JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
#   XINYI_PLATFORM_ENCRYPTION_KEY=$(python -c "import secrets; print(secrets.token_hex(16))")
#   XINYI_PLATFORM_ADMIN_PASSWORD=AdminPwd123!

uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn xinyi_platform.main:app --reload --port 8000
```

## Verification

### Browser
1. http://localhost:8000/login → log in as admin (password from .env)
2. /account → verify username shown
3. /admin/users → see admin in table
4. Create user "alice" with password "AlicePwd123!"
5. /admin/clients → register client_id "test-cli" with redirect_uri "http://localhost:9000/callback"
6. Save the returned client_secret (only shown once)
7. Logout, login as alice
8. Verify alice cannot access /admin/users (403)

### curl (OAuth2 flow)

```bash
# Login as alice (returns token + sets cookie)
curl -s -c /tmp/cookies.txt -X POST http://localhost:8000/login \
  -H 'Content-Type: application/json' \
  -d '{"provider":"local","username":"alice","password":"AlicePwd123!"}'

# Hit /oauth/authorize with alice's cookie
curl -i -b /tmp/cookies.txt \
  "http://localhost:8000/oauth/authorize?response_type=code&client_id=test-cli&redirect_uri=http://localhost:9000/callback&state=xyz"
# Expect: 303 to http://localhost:9000/callback?code=<code>&state=xyz
# Capture the code from the Location header

# Exchange code for tokens
curl -i -X POST http://localhost:8000/oauth/token \
  -H 'Content-Type: application/json' \
  -d "{
    \"grant_type\":\"authorization_code\",
    \"code\":\"$CODE\",
    \"client_id\":\"test-cli\",
    \"client_secret\":\"<paste from step 6>\",
    \"redirect_uri\":\"http://localhost:9000/callback\"
  }"
# Expect: JSON with access_token, refresh_token, user info

# Call internal API as the test client
curl -X POST http://localhost:8000/internal/users/batch-get \
  -H "X-Client-Id: test-cli" \
  -H "X-Client-Secret: <paste from step 6>" \
  -H "Content-Type: application/json" \
  -d "{\"ids\":[\"<alice uuid>\"]}"
# Expect: {"users": {"<alice uuid>": {"username":"alice", ...}}}
```

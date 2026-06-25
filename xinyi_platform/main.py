import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete

from xinyi_platform.config import Settings
from xinyi_platform.db import create_engine, create_session_factory
from xinyi_platform.models.oauth_code import OAuthCode
from xinyi_platform.models.token_revocation import TokenRevocation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings()

PLATFORM_NAV_MENU = [
    {
        "type": "section",
        "label": "账户",
        "items": [
            {"id": "account", "label": "我的账户", "href": "/xinyi/account"},
        ],
    },
    {
        "type": "section",
        "label": "管理",
        "require_admin": True,
        "items": [
            {"id": "users",          "label": "用户",       "href": "/xinyi/admin/users"},
            {"id": "clients",        "label": "业务接入",   "href": "/xinyi/admin/clients"},
            {"id": "audit_logs",     "label": "审计日志",   "href": "/xinyi/admin/audit-logs"},
            {"id": "login_history",  "label": "登录历史",   "href": "/xinyi/admin/login-history"},
        ],
    },
]


class AppState:
    def __init__(self):
        self.engine = None
        self.session_factory = None
        self.scheduler = None
        self.settings = None


app_state = AppState()


async def _cleanup_expired_tokens(session_factory):
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        await session.execute(delete(OAuthCode).where(OAuthCode.expires_at < now))
        await session.execute(delete(TokenRevocation).where(TokenRevocation.expires_at < now))
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_state.settings = settings
    app_state.engine = create_engine(settings)
    app_state.session_factory = create_session_factory(app_state.engine)

    async with app_state.session_factory() as session:
        from xinyi_platform.startup import seed_admin_if_absent
        await seed_admin_if_absent(session, settings)

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _cleanup_expired_tokens,
        "interval",
        hours=1,
        args=[app_state.session_factory],
        id="cleanup-expired-tokens",
        replace_existing=True,
    )
    scheduler.start()
    app_state.scheduler = scheduler

    yield

    scheduler.shutdown(wait=False)
    await app_state.engine.dispose()


app = FastAPI(title="xinyi-platform", version="0.1.0", lifespan=lifespan)

from xinyi_platform.ui_common import install_ui

install_ui(
    app,
    current_service="platform",
    nav_menu=PLATFORM_NAV_MENU,
    brand=settings.brand_name,
    platform_url=settings.base_url,
    manager_url=settings.manager_url,
    service_prefix="/xinyi",
)

app.mount("/xinyi/static", StaticFiles(directory="xinyi_platform/static"), name="static")

from xinyi_platform.api import (  # noqa: E402
    admin_audit, admin_clients, admin_login_history, admin_users,
    cas, internal, login, logout, me, oauth, password, register,
)

app.include_router(login.router, prefix="/xinyi")
app.include_router(logout.router, prefix="/xinyi")
app.include_router(me.router, prefix="/xinyi")
app.include_router(register.router, prefix="/xinyi")
app.include_router(password.router, prefix="/xinyi")
app.include_router(cas.router, prefix="/xinyi")
app.include_router(oauth.router, prefix="/xinyi")
app.include_router(internal.router, prefix="/xinyi")
app.include_router(admin_users.router, prefix="/xinyi")
app.include_router(admin_clients.router, prefix="/xinyi")
app.include_router(admin_audit.router, prefix="/xinyi")
app.include_router(admin_login_history.router, prefix="/xinyi")


@app.get("/xinyi/")
async def root():
    return RedirectResponse(url="/xinyi/account")


@app.get("/xinyi/health")
async def health():
    return {"status": "ok"}


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

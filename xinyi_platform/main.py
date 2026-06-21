from contextlib import asynccontextmanager

from fastapi import FastAPI

from xinyi_platform.config import Settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    app.state.settings = settings
    yield


app = FastAPI(title="xinyi-platform", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


from xinyi_platform.api import login, logout, me  # noqa: E402

app.include_router(login.router)
app.include_router(logout.router)
app.include_router(me.router)


from xinyi_platform.api import register, password  # noqa: E402

app.include_router(register.router)
app.include_router(password.router)


from xinyi_platform.api import cas  # noqa: E402

app.include_router(cas.router)


from xinyi_platform.api import oauth  # noqa: E402

app.include_router(oauth.router)

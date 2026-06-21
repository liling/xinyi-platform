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

from fastapi import APIRouter, Cookie, Request
from fastapi.responses import JSONResponse, RedirectResponse

router = APIRouter(tags=["auth"])


@router.post("/logout")
async def logout(request: Request, xinyi_session: str | None = Cookie(default=None)):
    resp = JSONResponse(content={"ok": True})
    resp.delete_cookie("xinyi_session", path="/")
    return resp


@router.get("/logout")
async def logout_get(request: Request):
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("xinyi_session", path="/")
    return resp

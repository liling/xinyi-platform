from fastapi import APIRouter, Cookie, Form, Query, Request
from fastapi.responses import RedirectResponse

router = APIRouter(tags=["auth"])


@router.post("/logout")
async def logout(
    request: Request,
    return_to: str = Form("/login"),
    xinyi_session: str | None = Cookie(default=None),
):
    resp = RedirectResponse(url=return_to, status_code=303)
    resp.delete_cookie("xinyi_session", path="/")
    return resp


@router.get("/logout")
async def logout_get(
    request: Request,
    return_to: str = Query("/login"),
):
    resp = RedirectResponse(url=return_to, status_code=303)
    resp.delete_cookie("xinyi_session", path="/")
    return resp

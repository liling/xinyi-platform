from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from xinyi_platform.auth.csrf import generate_csrf_token, verify_csrf


class CsrfMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        token = request.cookies.get("xinyi_csrf") or generate_csrf_token()
        request.state.csrf_token = token

        response = await call_next(request)

        if not request.cookies.get("xinyi_csrf"):
            response.set_cookie(
                "xinyi_csrf", token,
                httponly=False, samesite="lax", path="/",
            )
        return response


async def verify_csrf_token(request: Request) -> None:
    cookie_token = request.cookies.get("xinyi_csrf", "")

    submitted = ""
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        submitted = form.get("csrf_token", "")

    if not submitted:
        submitted = request.headers.get("x-csrf-token", "")

    if not verify_csrf(cookie_token, submitted):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed",
        )

"""install_ui: wire shared UI assets and globals into a FastAPI app."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from .registry import PRODUCTS

_HERE = Path(__file__).resolve().parent
_STATIC_DIR = _HERE / "static"
_TEMPLATE_DIR = _HERE / "templates"


def _resolve_products(*, platform_url: str, manager_url: str | None) -> list[dict]:
    resolved: list[dict] = []
    for p in PRODUCTS:
        url = p["url_template"].format(
            platform_url=platform_url,
            manager_url=manager_url or "",
        )
        resolved.append({**p, "url_template": None, "url": url})
    return resolved


def install_ui(
    app: FastAPI,
    *,
    current_service: str,
    nav_menu: list[dict],
    brand: str,
    platform_url: str,
    manager_url: str | None = None,
) -> None:
    """Install shared UI: Jinja globals, templates loader, static files mount."""
    app.state.ui = {
        "current_service": current_service,
        "nav_menu": nav_menu,
        "brand": brand,
        "platform_url": platform_url,
        "manager_url": manager_url,
        "products": _resolve_products(
            platform_url=platform_url, manager_url=manager_url
        ),
        "template_dir": str(_TEMPLATE_DIR),
    }

    app.mount(
        "/_ui/static",
        StaticFiles(directory=str(_STATIC_DIR)),
        name="ui-static",
    )


def ui_jinja_globals(request: Request) -> dict:
    """Helper to be used by business Jinja2Templates to expose ui_common state.

    Usage in a business app::

        from fastapi.templating import Jinja2Templates
        from xinyi_platform.ui_common import install_ui, ui_jinja_globals

        templates = Jinja2Templates(directory="my_app/templates")
        templates.env.globals.update(**ui_jinja_globals_factory(app))

    For FastAPI `Request`-based resolution we attach this helper and let
    business code wire its own Jinja env; see Task 3/4 for an example.
    """
    ui = request.app.state.ui
    return {
        "current_service": ui["current_service"],
        "nav_menu": ui["nav_menu"],
        "brand": ui["brand"],
        "platform_url": ui["platform_url"],
        "manager_url": ui["manager_url"],
        "products": ui["products"],
    }

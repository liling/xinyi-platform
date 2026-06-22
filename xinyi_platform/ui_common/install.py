"""install_ui: wire shared UI assets and globals into a FastAPI app."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
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
    """Install shared UI: Jinja globals, templates loader, static files mount.

    Args:
        app: FastAPI instance to wire into.
        current_service: which key in PRODUCTS represents this service
            (used to mark active in topbar/sidebar). One of "platform",
            "hindsight-manager", or future business ids.
        nav_menu: list-of-sections describing this service's sidebar.
        brand: brand label shown next to logo in topbar.
        platform_url: base URL of the platform (xinyi-platform) service.
        manager_url: base URL of hindsight-manager (required for the
            platform service to render HM entry in the switcher; business
            services may leave None).

    Stores resolved config on `app.state.ui` so routers and Jinja globals
    can access it later. Mounts `/​_ui/static` so every service can serve
    ui.css at the same path.
    """
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

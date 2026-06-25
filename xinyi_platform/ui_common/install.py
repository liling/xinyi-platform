"""install_ui: wire shared UI assets and globals into a FastAPI app."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

_HERE = Path(__file__).resolve().parent
_STATIC_DIR = _HERE / "static"
_TEMPLATE_DIR = _HERE / "templates"


def install_ui(
    app: FastAPI,
    *,
    current_service: str,
    nav_menu: list[dict],
    brand: str,
    platform_url: str,
    service_prefix: str = "",
) -> None:
    """Install shared UI: Jinja globals, templates loader, static files mount.

    products starts empty; populate via app.state.ui["products"] in lifespan
    using service_discovery.build_product_list().
    """
    app.state.ui = {
        "current_service": current_service,
        "nav_menu": nav_menu,
        "brand": brand,
        "platform_url": platform_url,
        "service_prefix": service_prefix,
        "products": [],
        "manager_url": "",
        "template_dir": str(_TEMPLATE_DIR),
    }

    app.mount(
        f"{service_prefix}/_ui/static",
        StaticFiles(directory=str(_STATIC_DIR)),
        name="ui-static",
    )


def ui_jinja_globals(request: Request) -> dict:
    ui = request.app.state.ui
    return {
        "current_service": ui["current_service"],
        "nav_menu": ui["nav_menu"],
        "brand": ui["brand"],
        "platform_url": ui["platform_url"],
        "products": ui["products"],
        "manager_url": ui.get("manager_url", ""),
        "service_prefix": ui.get("service_prefix", ""),
    }

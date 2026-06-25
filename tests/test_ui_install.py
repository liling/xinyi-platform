from fastapi import FastAPI

from xinyi_platform.ui_common import install_ui


def test_install_ui_registers_globals_and_static():
    app = FastAPI()
    install_ui(
        app,
        current_service="hindsight-manager",
        nav_menu=[
            {"type": "section", "label": "业务", "items": [
                {"id": "dashboard", "label": "仪表盘", "href": "/dashboard"},
            ]},
        ],
        brand="Hindsight",
        platform_url="http://platform.test",
    )

    assert "/_ui/static" in { getattr(r, "path", "") for r in app.routes }

    assert app.state.ui["current_service"] == "hindsight-manager"
    assert app.state.ui["brand"] == "Hindsight"
    assert app.state.ui["products"] == []


def test_install_ui_requires_main_app_and_current_service():
    import pytest
    with pytest.raises(TypeError):
        install_ui()  # type: ignore[call-arg]


def test_ui_assets_present():
    from pathlib import Path
    from xinyi_platform.ui_common import install  # noqa
    base = Path(install.__file__).resolve().parent
    assert (base / "static" / "ui.css").exists()
    assert (base / "templates" / "ui" / "base.html").exists()
    assert (base / "templates" / "ui" / "app_shell.html").exists()
    assert (base / "templates" / "ui" / "auth_shell.html").exists()
    assert (base / "templates" / "ui" / "topbar.html").exists()
    assert (base / "templates" / "ui" / "sidebar.html").exists()
    assert (base / "templates" / "ui" / "topbar.html").exists()
    assert not (base / "templates" / "ui" / "product_switcher.html").exists()

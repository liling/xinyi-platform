from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from xinyi_platform.ui_common import install_ui, PRODUCTS


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
        manager_url="http://hm.test",
    )

    routes = {r.path: r for r in app.routes}
    assert "/_ui/static" in { getattr(r, "path", "") for r in app.routes }

    # Jinja2 globals — 验证可以通过创建一个 Jinja2Templates 实例后 env 是否带预期 globals
    # install_ui 在 app.state 上缓存了配置,这里验证 app.state.ui
    assert app.state.ui["current_service"] == "hindsight-manager"
    assert app.state.ui["brand"] == "Hindsight"
    products = app.state.ui["products"]
    assert any(p["id"] == "platform" for p in products)
    assert any(p["id"] == "hindsight-manager" for p in products)
    hm_entry = next(p for p in products if p["id"] == "hindsight-manager")
    assert hm_entry["url"] == "http://hm.test/dashboard"
    platform_entry = next(p for p in products if p["id"] == "platform")
    assert platform_entry["url"] == "http://platform.test/account"


def test_products_constant_shape():
    assert len(PRODUCTS) >= 2
    for p in PRODUCTS:
        assert {"id", "label", "subtitle", "kind", "url_template"} <= set(p.keys())
        assert p["kind"] in {"platform", "business"}


def test_install_ui_requires_main_app_and_current_service():
    import pytest
    with pytest.raises(TypeError):
        install_ui()  # type: ignore[call-arg]

from fastapi.testclient import TestClient

from xinyi_platform.main import app


def test_app_has_ui_state_configured():
    client = TestClient(app)
    assert app.state.ui["current_service"] == "platform"
    assert app.state.ui["brand"] == "平台"
    assert app.state.ui["products"] == []


def test_static_ui_css_served():
    client = TestClient(app)
    resp = client.get("/xinyi/_ui/static/ui.css")
    assert resp.status_code == 200


def test_sidebar_renders_product_switcher():
    from jinja2 import ChoiceLoader, Environment, FileSystemLoader
    from xinyi_platform.ui_common.install import _TEMPLATE_DIR as UI_TEMPLATE_DIR

    env = Environment(loader=ChoiceLoader([
        FileSystemLoader(UI_TEMPLATE_DIR),
    ]))
    template = env.get_template("ui/sidebar.html")

    html = template.render(
        request=type("R", (), {"url": type("U", (), {"path": "/xinyi/account"})()})(),
        current_user={"username": "alice", "role": "member"},
        brand="平台",
        service_prefix="/xinyi",
        products=[
            {
                "id": "platform",
                "label": "平台账户中心",
                "subtitle": "用户 · 审计 · 登录历史",
                "url": "http://xinyi.test/xinyi/account",
                "kind": "platform",
                "is_current": True,
            },
            {
                "id": "hindsight-manager",
                "label": "Hindsight Manager",
                "subtitle": "RAG 记忆库",
                "url": "http://hm.test/hindsight/dashboard",
                "kind": "business",
                "is_current": False,
            },
        ],
    )
    assert 'class="product-switcher"' in html
    assert "平台账户中心" in html
    assert "Hindsight Manager" in html
    assert "http://hm.test/hindsight/dashboard" in html

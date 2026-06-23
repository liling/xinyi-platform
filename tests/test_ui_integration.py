from fastapi.testclient import TestClient

from xinyi_platform.main import app


def test_app_has_ui_state_configured():
    client = TestClient(app)
    assert app.state.ui["current_service"] == "platform"
    assert app.state.ui["brand"] == "xinyi"
    assert any(p["id"] == "platform" for p in app.state.ui["products"])


def test_static_ui_css_served():
    client = TestClient(app)
    resp = client.get("/_ui/static/ui.css")
    assert resp.status_code == 200

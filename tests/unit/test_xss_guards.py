"""Structural XSS guards — borrowed from docupipe-manager's test_xss_fix.py idea.

These tests forbid the patterns that introduced the logout reflective XSS:
  1. Bare jinja2.Environment() usage (autoescape defaults to False). All
     rendering must go through make_templates()/Jinja2Templates, which enables
     autoescape for .html.
  2. Raw {{ return_to }} in a JS context. Data interpolated into <script> must
     be JSON-encoded via | tojson.

Uses AST (not regex) so explanatory comments mentioning these APIs are safe.
"""
import ast
from pathlib import Path

from xinyi_platform.jinja_env import make_templates

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PKG = _PROJECT_ROOT / "xinyi_platform"


def _bare_environment_calls(pkg: Path) -> list[str]:
    offenders = []
    for py in pkg.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == "Environment":
                offenders.append(str(py.relative_to(_PROJECT_ROOT)))
            elif isinstance(func, ast.Attribute) and func.attr == "Environment":
                offenders.append(str(py.relative_to(_PROJECT_ROOT)))
    return offenders


class TestNoBareJinjaEnvironment:
    def test_no_bare_environment_call_in_package(self):
        offenders = _bare_environment_calls(_PKG)
        assert not offenders, (
            "Bare jinja2.Environment() call found — it defaults to "
            "autoescape=False (XSS vector). Use make_templates() instead. "
            "Offenders: " + ", ".join(offenders)
        )

    def test_make_templates_autoescapes_html(self):
        env = make_templates().env
        assert env.autoescape("logout.html") is True
        assert env.autoescape("login.html") is True


class TestLogoutTemplateSafeInterpolation:
    def test_return_to_is_json_encoded(self):
        src = (_PKG / "templates" / "logout.html").read_text(encoding="utf-8")
        assert "{{ return_to }}" not in src, (
            "return_to must be JSON-encoded ({{ return_to | tojson }}) — it is "
            "interpolated into a <script> JS string context."
        )
        assert "{{ return_to | tojson }}" in src

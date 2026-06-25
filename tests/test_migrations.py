import importlib.util
from pathlib import Path

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "xinyi_platform"
    / "migrations"
    / "versions"
    / "006_relative_client_urls.py"
)


def _load_migration_006():
    spec = importlib.util.spec_from_file_location("migration_006", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_strip_base_url_strips_matching_prefix():
    migration = _load_migration_006()
    base_url = "http://hm:8001/hindsight"
    assert migration._strip_base_url("http://hm:8001/hindsight/auth/callback", base_url) == "/auth/callback"
    assert migration._strip_base_url("http://hm:8001/hindsight/auth/logout", base_url) == "/auth/logout"


def test_strip_base_url_preserves_relative_paths():
    migration = _load_migration_006()
    base_url = "http://hm:8001/hindsight"
    assert migration._strip_base_url("/already/relative", base_url) == "/already/relative"


def test_strip_base_url_handles_none():
    migration = _load_migration_006()
    base_url = "http://hm:8001/hindsight"
    assert migration._strip_base_url(None, base_url) is None


def test_strip_base_url_preserves_non_matching_urls():
    migration = _load_migration_006()
    base_url = "http://hm:8001/hindsight"
    assert migration._strip_base_url("http://other:9999/path", base_url) == "http://other:9999/path"

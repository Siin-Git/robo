"""Deployment regression: preserve local defaults, enforce HTTPS when configured."""
import pytest

from src.api.routers.auth import _cookie_conf
from src.db.config import ROOT, get_database_url


@pytest.mark.parametrize("value,expected", [("true", True), ("1", True), ("false", False), ("0", False), ("", False)])
def test_local_demo_secure_cookie_override(monkeypatch, value, expected):
    monkeypatch.setenv("APP_PROFILE", "local")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", value)
    assert _cookie_conf()[-1] is expected


def test_demo_disk_path_is_isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_PROFILE", "local")
    monkeypatch.setenv("CAPSTONE_DEMO", "1")
    monkeypatch.setenv("CAPSTONE_DATA_DIR", str(tmp_path))
    assert get_database_url("sqlite") == f"sqlite:///{tmp_path / 'capstone_demo.db'}"
    monkeypatch.delenv("CAPSTONE_DATA_DIR")
    assert get_database_url("sqlite") == f"sqlite:///{ROOT / 'data' / 'capstone_demo.db'}"
    monkeypatch.setenv("CAPSTONE_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("CAPSTONE_DEMO")
    assert get_database_url("sqlite") == f"sqlite:///{ROOT / 'data' / 'forward_local.db'}"

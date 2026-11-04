"""Server account import uses hashes and preserves saved work across restarts."""
import json

import pytest
from sqlalchemy import select, func

from src.api.services import auth_service as auth
from src.db.models.user import User
from src.db.models.demo_cohort import DemoSlot
from src.local.capstone import COHORT_SIZE
from src.local.capstone import EMAILS
from src.local.lab_meeting import prepare_from_environment


@pytest.fixture
def server_accounts(env, monkeypatch):
    monkeypatch.setenv("APP_PROFILE", "local")
    monkeypatch.setenv("CAPSTONE_DEMO", "1")
    monkeypatch.setenv("CAPSTONE_MARKET_COMPARISON", "1")
    monkeypatch.setenv("DATABASE_BACKEND", "sqlite")
    data = {"cohort_id": "lab-hosted", "accounts": [
        {"email": email, "password_hash": auth._hasher().hash(f"test-server-password-{i:02d}")}
        for i, email in enumerate(EMAILS)]}
    monkeypatch.setenv("CAPSTONE_LAB_ACCOUNTS_JSON", json.dumps(data))
    return env, data


def test_import_login_and_preserve_changed_password_and_draft(server_accounts):
    env, data = server_accounts
    with env.factory() as s:
        assert prepare_from_environment(s)
        s.commit()
        for i, e in enumerate(data["accounts"]):
            user, _, _ = auth.login(s, e["email"], f"test-server-password-{i:02d}")
            assert user["email"] == e["email"]
        first = s.scalar(select(User).where(User.email_normalized == EMAILS[0]))
        replacement = auth._hasher().hash("a-new-user-selected-password")
        first.password_hash = replacement
        slot = s.scalar(select(DemoSlot).where(DemoSlot.user_id == first.user_id))
        slot.draft_json = {"core_id": "CORE_V0.3", "theme_ids": ["ai"], "current_step": "themes"}
        s.commit()
        assert not prepare_from_environment(s)
        assert first.password_hash == replacement and slot.draft_json["theme_ids"] == ["ai"]
        assert s.scalar(select(func.count()).select_from(User)) == COHORT_SIZE


@pytest.mark.parametrize("change", ["missing", "duplicate", "plaintext", "wrong_hash"])
def test_invalid_server_settings_do_not_create_accounts(server_accounts, monkeypatch, change):
    env, data = server_accounts
    if change == "missing":
        data["accounts"].pop()
    elif change == "duplicate":
        data["accounts"][-1] = data["accounts"][0]
    elif change == "plaintext":
        data["accounts"][0]["password"] = "must-never-be-imported"
    else:
        data["accounts"][0]["password_hash"] = "invalid"
    monkeypatch.setenv("CAPSTONE_LAB_ACCOUNTS_JSON", json.dumps(data))
    with env.factory() as s:
        with pytest.raises(ValueError, match="Invalid CAPSTONE"):
            prepare_from_environment(s)
        assert s.scalar(select(func.count()).select_from(User)) == 0


def test_server_import_refuses_live_profile(server_accounts, monkeypatch):
    env, _ = server_accounts
    monkeypatch.setenv("APP_PROFILE", "live")
    with env.factory() as s:
        with pytest.raises(ValueError, match="isolated"):
            prepare_from_environment(s)
        assert s.scalar(select(func.count()).select_from(User)) == 0

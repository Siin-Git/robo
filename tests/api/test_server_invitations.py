"""Server-only invitation configuration never resets saved identities or drafts."""
import json
import secrets

import pytest
from sqlalchemy import select

from src.api.services.auth_service import hash_token
from src.db.models.demo_cohort import DemoSlot
from src.local.demo_cohort import prepare_from_environment
from src.local.seed_capstone import seed


def configure(env, monkeypatch):
    monkeypatch.setenv("APP_PROFILE", "local")
    monkeypatch.setenv("CAPSTONE_DEMO", "1")
    code = secrets.token_urlsafe(32)
    data = {"cohort_id": "server-config", "invitations": [
        {"email": "reserved@example.com", "invite_sha256": hash_token(code)}]}
    monkeypatch.setenv("CAPSTONE_INVITATIONS_JSON", json.dumps(data))
    with env.factory() as s:
        seed(s)
        assert prepare_from_environment(s)["unchanged"] is False
        s.commit()
    return data, code


def test_server_config_is_idempotent_after_registration(env, monkeypatch):
    data, code = configure(env, monkeypatch)
    c = env.client
    password = secrets.token_urlsafe(24)
    assert c.post("/api/v1/auth/register", json={"email": "reserved@example.com",
        "password": password, "display_name": "Server invite", "invitation_code": code}).status_code == 201
    with env.factory() as s:
        slot = s.scalar(select(DemoSlot))
        slot.draft_json = {"reason": "keep my draft"}
        user_id = slot.user_id
        s.commit()
        assert prepare_from_environment(s)["unchanged"] is True
        s.commit()
        s.refresh(slot)
        assert slot.user_id == user_id and slot.draft_json == {"reason": "keep my draft"}
        assert slot.invite_hash != code
        data["invitations"][0]["invite_sha256"] = hash_token(secrets.token_urlsafe(32))
        monkeypatch.setenv("CAPSTONE_INVITATIONS_JSON", json.dumps(data))
        with pytest.raises(ValueError, match="differs"):
            prepare_from_environment(s)
        assert slot.user_id == user_id


@pytest.mark.parametrize("raw", ['{}', 'null', 'not-json', '{"cohort_id":"a","invitations":[]}'])
def test_invalid_configuration_fails_closed_without_echo(env, monkeypatch, raw):
    monkeypatch.setenv("APP_PROFILE", "local")
    monkeypatch.setenv("CAPSTONE_DEMO", "1")
    monkeypatch.setenv("CAPSTONE_INVITATIONS_JSON", raw)
    with env.factory() as s, pytest.raises(ValueError, match="Invalid CAPSTONE_INVITATIONS_JSON"):
        prepare_from_environment(s)


def test_server_config_cannot_switch_active_cohort_or_run_in_live(env, monkeypatch):
    data, _ = configure(env, monkeypatch)
    data["cohort_id"] = "another-group"
    monkeypatch.setenv("CAPSTONE_INVITATIONS_JSON", json.dumps(data))
    with env.factory() as s:
        with pytest.raises(ValueError, match="active cohort"):
            prepare_from_environment(s)
        monkeypatch.setenv("APP_PROFILE", "live")
        with pytest.raises(ValueError, match="isolated"):
            prepare_from_environment(s)

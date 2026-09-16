"""Shared service helpers: conversions, config/frozen readers, IDs, events."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def as_aware_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def as_date(x) -> date | None:
    if x is None:
        return None
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    return date.fromisoformat(str(x)[:10])


def fnum(x) -> float | None:
    if x is None:
        return None
    if isinstance(x, Decimal):
        return float(x)
    return float(x)


def load_forward_cfg() -> dict:
    with open(ROOT / "config" / "forward_v0.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def frozen_bundle() -> tuple[dict, dict]:
    d = ROOT / "outputs" / "frozen" / "CORE_V0.3"
    weights = json.loads((d / "weights.json").read_text(encoding="utf-8"))
    meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
    return {k: float(v) for k, v in weights.items()}, meta


def new_id(session, prefix: str, width: int = 3) -> str:
    from ...db.repositories.forward import next_id
    return next_id(session, prefix, width)


def log_event(session, event_type: str, model_version: str, participant_id=None,
              account_id=None, payload=None) -> str:
    from ...db.repositories.forward import EventRepository
    eid = new_id(session, "E", 6)
    EventRepository(session).append(
        event_id=eid, event_type=event_type, participant_id=participant_id,
        account_id=account_id, timestamp=now_utc(),
        payload_json=dict(payload or {}), model_version=model_version)
    return eid


def latest_price_date(session) -> date | None:
    from ...db.repositories.forward import PriceRepository
    dates = PriceRepository(session).dates()
    days = [as_date(d) for d in dates]
    return max(days) if days else None

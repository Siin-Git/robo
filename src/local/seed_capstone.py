"""Idempotent synthetic demo fixture; isolated from every existing database.

Run: python -m src.local.seed_capstone
NAV paths are illustrative scenarios, not backtests or newly simulated trades.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import yaml
from sqlalchemy import select

from .capstone import COHORT, EMAILS, PASSWORD


def paths():
    dates = pd.bdate_range("2026-04-01", "2026-09-11")
    x = np.arange(len(dates) - 1)
    core_r = .00038 + .0035 * np.sin(x * .47) + .002 * np.cos(x * .19)
    # Fixed display scenarios per theme; shared theme pairs always share a path.
    params = {
        "semiconductor": (.0006, .012, .30), "ai": (.00045, .010, .8),
        "defense": (.00035, .002, 1.2), "nuclear": (-.00020, .011, 2.0),
        "power_grid": (.00015, .001, 1.8), "cybersecurity": (.00012, .003, 2.8),
        "robotics": (-.00035, .008, 3.4), "biotech": (-.0008, .014, 4.1),
        "cloud_data_center": (-.00025, .006, 4.8),
    }
    def nav(returns):
        return np.r_[100., 100 * np.cumprod(1 + returns)]
    personal = []
    for _, themes in COHORT:
        changes = [drift + amplitude * np.sin(x * .47 + phase)
                   for drift, amplitude, phase in (params[t] for t in themes)]
        personal.append(nav(core_r + np.mean(changes, axis=0)))
    # Small bounded fixture irregularity removes perfectly smooth sine waves.
    # This is display data, not a price model. Preserve both endpoints exactly.
    rng = np.random.default_rng(20260919)
    common = rng.uniform(-.0015, .0015, len(dates))
    common[[0, -1]] = 0.
    theme_noise = {t: rng.uniform(-.001, .001, len(dates))
                   for t in sorted({t for _, themes in COHORT for t in themes})}
    for i, (_, themes) in enumerate(COHORT):
        adjustment = common + np.mean([theme_noise[t] for t in themes], axis=0)
        adjustment[[0, -1]] = 0.
        personal[i] *= 1 + adjustment
    return dates, nav(core_r) * (1 + common), personal


def seed(session):
    from ..api.services import auth_service as auth, _common as C
    from ..db.models.user import User
    from ..db.models.participant import Participant
    from ..db.models.account import Account
    from ..db.models.nav import NavDaily
    from ..db.models.portfolio import PortfolioTarget
    from ..db.models.view import View
    from ..db.models.theme import Theme
    from ..db.config import ROOT
    from ..forward.portfolio import theme_target_weights, fund_from_equities

    cfg = C.load_forward_cfg()
    ft = cfg["forward_test"]
    frozen, _ = C.frozen_bundle()
    with open(ROOT / "config/themes_v01.yaml", encoding="utf-8") as f:
        for item in yaml.safe_load(f)["themes"]:
            data = {k: v for k, v in item.items() if k in Theme.__table__.columns.keys()}
            for key in ("valid_from", "valid_to"):
                if isinstance(data.get(key), str): data[key] = date.fromisoformat(data[key])
            if session.get(Theme, item["theme_id"]) is None: session.add(Theme(**data))
    session.flush()
    dates, core_nav, personal_nav = paths()
    start = dates[0].date()
    created = datetime(2026, 4, 1, tzinfo=timezone.utc)
    for i, ((name, themes), email) in enumerate(zip(COHORT, EMAILS), 1):
        user = session.scalar(select(User).where(User.email_normalized == email))
        if user is not None:
            # A repeated run never overwrites credentials, history, or selections.
            continue
        info = auth.register(session, email, PASSWORD, name)
        pid = info["participant_id"]
        session.get(Participant, pid).join_date = start
        tw = theme_target_weights([f"theme:{t}" for t in themes], cfg)
        funded, _ = fund_from_equities(dict(frozen), tw)
        weights = {**funded, **tw}
        for account in session.scalars(select(Account).where(Account.participant_id == pid)):
            account.inception_date = start
            target = session.scalar(select(PortfolioTarget).where(PortfolioTarget.account_id == account.account_id))
            target.effective_date = start
            target.created_at = created
            target.weights_json = dict(frozen) if account.account_type == "core" else weights
            target.kind = account.account_type
            nav = core_nav if account.account_type == "core" else personal_nav[i - 1]
            for j, d in enumerate(dates):
                session.add(NavDaily(
                    account_id=account.account_id, date=d.date(), nav=float(nav[j]),
                    nav_base100=float(nav[j]), daily_return=float(nav[j]/nav[j-1]-1) if j else 0.,
                    cumulative_return=float(nav[j]/100-1), cash_balance=0,
                    stale_price_flag=False, nav_status="OK",
                    benchmark_version=ft["benchmark_version"], theme_universe_version=ft["theme_universe_version"],
                    risk_model_version=ft["risk_model_version"], execution_rule_version=ft["execution_rule_version"],
                ))
        for k, theme in enumerate(themes):
            session.add(View(view_id=f"CD{i:02d}V{k}", participant_id=pid, theme_id=theme,
                status="hold", submitted_at=created, effective_at=start, end_at=None,
                reason="사전 배정된 시연용 View · 가상 NAV", theme_universe_version=ft["theme_universe_version"],
                cycle_week=start, cycle_date=start))
        session.flush()
    return len(EMAILS)


def main():
    # Set before importing DB configuration. No caller can redirect this seed to live.
    os.environ.update(APP_PROFILE="local", DATABASE_BACKEND="sqlite", CAPSTONE_DEMO="1")
    from ..db.session import create_app_engine, session_factory
    from ..db.base import Base
    engine = create_app_engine()
    Base.metadata.create_all(engine)
    with session_factory(engine)() as session:
        seed(session)
        session.commit()
    print("13 demo accounts ready · data/capstone_demo.db")
    print(f"capstone01@example.com … capstone13@example.com / {PASSWORD}")


if __name__ == "__main__":
    main()

"""Performance application service.

Numbers come from the existing metric functions
(``src.forward.metrics``); this layer only fetches rows via repositories.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import select

from ...forward.metrics import perf_metrics, tracking_ir
from ...db.models.account import Account as _A
from ...db.models.holding import Holding as _H
from ...db.models.nav import NavDaily as _N
from ...db.models.participant import Participant as _P
from ...db.models.price import PriceDaily as _Px
from ...db.models.trade import Trade as _T
from ..errors import not_found
from . import _common as C


def _accounts(session, participant_id: str):
    rows = list(session.scalars(select(_A).where(_A.participant_id == participant_id)))
    if not rows:
        raise not_found("PARTICIPANT_NOT_FOUND", f"Unknown participant {participant_id}.")
    personal = next((a for a in rows if a.account_type == "personal"), None)
    core = next((a for a in rows if a.account_type == "core"), None)
    return personal, core


def _frame(session, account_id: str | None) -> pd.DataFrame:
    if account_id is None:
        return pd.DataFrame()
    rows = list(session.scalars(select(_N).where(_N.account_id == account_id)
                                .order_by(_N.date)))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([{"date": C.as_date(r.date), "nav": C.fnum(r.nav),
                        "nav_base100": C.fnum(r.nav_base100),
                        "daily_return": C.fnum(r.daily_return)} for r in rows])
    return df.set_index(pd.to_datetime(df.pop("date"))).sort_index()


def summary(session, participant_id: str, start=None, end=None) -> dict:
    personal, core = _accounts(session, participant_id)
    nav = _frame(session, personal.account_id if personal else None)
    if start:
        nav = nav[nav.index >= pd.Timestamp(start)]
    if end:
        nav = nav[nav.index <= pd.Timestamp(end)]
    pm = perf_metrics(nav)
    if pm.get("status") == "INSUFFICIENT_HISTORY" and nav.empty:
        return {"status": "INSUFFICIENT_HISTORY",
                "metrics": {"cumulative_return": None, "mdd": None,
                            "tracking_error": None, "information_ratio": None}}
    out_metrics = {k: (C.fnum(v) if not isinstance(v, str) else v)
                   for k, v in pm.items() if k != "status"}
    if core is not None and not nav.empty:
        ti = tracking_ir(nav, _frame(session, core.account_id))
        out_metrics["tracking_error"] = C.fnum(ti.get("tracking_error"))
        out_metrics["information_ratio"] = C.fnum(ti.get("information_ratio"))
        out_metrics["active_cumulative"] = C.fnum(ti.get("active_cumulative"))
    return {"status": pm.get("status", "OK"), "metrics": out_metrics}


def nav_history(session, participant_id: str) -> dict:
    """차트가 그리는 NAV 이력. 값은 **기준 100** 환산이다.

    ``nav_daily`` 에는 값이 둘 있다. ``nav`` 은 원화 평가액(초기자본 1억)이고
    ``nav_base100`` 은 운용 시작을 100 으로 놓은 지수다. 화면은 이 값을
    100 기준으로 읽어 수익률을 만든다.

    예전에는 ``nav`` 을 돌려줬다. 시연 DB 는 두 값이 같아서(가상 NAV 를
    base100 으로 넣는다) 우연히 맞았지만, 운용 기록을 같은 DB 에서 읽게 된
    뒤로 원화 금액이 그대로 들어가 화면에 99,642,385% 가 찍혔다.
    이름이 약속하는 대로 기준 100 값을 돌려준다.
    """
    personal, core = _accounts(session, participant_id)
    pn, cn = _frame(session, personal.account_id if personal else None), \
        _frame(session, core.account_id if core else None)
    idx = sorted(set(pn.index) | set(cn.index))
    items = []
    for d in idx:
        items.append({"date": d.date().isoformat(),
                      "personalized_nav": C.fnum(pn.loc[d, "nav_base100"]) if d in pn.index else None,
                      "core_nav": C.fnum(cn.loc[d, "nav_base100"]) if d in cn.index else None})
    return {"items": items}


def active_returns(session, participant_id: str) -> dict:
    personal, core = _accounts(session, participant_id)
    pn, cn = _frame(session, personal.account_id if personal else None), \
        _frame(session, core.account_id if core else None)
    idx = pn.index.intersection(cn.index)
    if len(idx) < 2:
        return {"daily": [], "weekly": None, "cumulative": None}
    pr = pn.loc[idx, "daily_return"].dropna()
    cr = cn.loc[idx, "daily_return"].dropna()
    jdx = pr.index.intersection(cr.index)
    if len(jdx) < 1:
        return {"daily": [], "weekly": None, "cumulative": None}
    active = (pr.loc[jdx] - cr.loc[jdx]).to_numpy(float)
    daily = [{"date": jdx[i].date().isoformat(), "active_return": float(active[i])}
             for i in range(len(active))]
    w = active[-5:] if len(active) >= 5 else active
    weekly = float((1 + w).prod() - 1.0) if len(w) else None
    cumulative = float((pn.loc[idx, "nav"].iloc[-1] / pn.loc[idx, "nav"].iloc[0]) /
                       (cn.loc[idx, "nav"].iloc[-1] / cn.loc[idx, "nav"].iloc[0]) - 1.0)
    return {"daily": daily[-60:], "weekly": weekly, "cumulative": cumulative}


def attribution(session, participant_id: str, start=None, end=None) -> dict:
    personal, core = _accounts(session, participant_id)
    if personal is None:
        raise not_found("PARTICIPANT_NOT_FOUND", f"Unknown participant {participant_id}.")
    holds = list(session.scalars(select(_H).where(_H.account_id == personal.account_id)
                                 .order_by(_H.date)))
    if not holds:
        return {"core_return": None, "active_return": None, "transaction_cost": None,
                "theme_contributions": []}
    pxrows = list(session.scalars(select(_Px).order_by(_Px.date)))
    px = pd.DataFrame([{"date": C.as_date(r.date), "asset": r.asset_id,
                        "price": C.fnum(r.price)} for r in pxrows])
    px = px.pivot(index="date", columns="asset", values="price").sort_index()
    px.index = pd.to_datetime(px.index)
    rets = px.pct_change()
    rdates = rets.index
    buckets: dict[str, float] = {}
    for d in sorted({C.as_date(h.date) for h in holds}):
        nxt = rdates[rdates > pd.Timestamp(d)]
        if len(nxt) == 0:
            continue
        r1 = rets.loc[nxt[0]]
        for h in [x for x in holds if C.as_date(x.date) == d]:
            a = h.asset_id
            c = float(h.weight) * float(r1[a]) if a in r1.index else 0.0
            key = ("theme:" + a.split(":", 1)[1]) if a.startswith("theme:") else "core"
            buckets[key] = buckets.get(key, 0.0) + (c if c == c else 0.0)
    nav = _frame(session, personal.account_id)
    total = float(nav["nav"].iloc[-1] / nav["nav"].iloc[0] - 1.0) if len(nav) >= 2 else 0.0
    costs = session.execute(select(_T.transaction_cost).where(
        _T.account_id == personal.account_id)).scalars().all()
    cost_drag = -sum(float(c or 0) for c in costs) / float(nav["nav"].iloc[0]) if len(nav) else 0.0
    core_ret = buckets.get("core", 0.0)
    themes = [{"theme_id": k.split(":", 1)[1], "contribution": v}
              for k, v in sorted(buckets.items()) if k.startswith("theme:")]
    return {"core_return": core_ret,
            "active_return": sum(v for k, v in buckets.items() if k != "core") + cost_drag,
            "transaction_cost": cost_drag, "theme_contributions": themes,
            "total_return": total,
            "residual": total - (sum(buckets.values()) + cost_drag)}


_RANK_BASIS = {"active_return", "cumulative", "ir", "mdd"}


def rankings(session, period: str = "weekly", basis: str = "active_return",
             comparison: str = "common_period") -> dict:
    if basis not in _RANK_BASIS:
        from ..errors import ApiError
        raise ApiError("INVALID_BASIS", f"basis must be one of {sorted(_RANK_BASIS)}.", 400)
    people = list(session.scalars(select(_P).where(_P.status == "active")
                                  .order_by(_P.participant_id)))
    rows = []
    theme_map: dict[str, list[str]] = {}
    for p in people:
        from ...db.models.view import View as _V
        theme_map[p.participant_id] = sorted({
            v.theme_id for v in session.scalars(select(_V).where(
                _V.participant_id == p.participant_id, _V.status.in_(["new", "hold"]),
                _V.end_at.is_(None)))})
    for p in people:
        personal = session.scalars(select(_A).where(
            _A.participant_id == p.participant_id, _A.account_type == "personal")).first()
        core = session.scalars(select(_A).where(
            _A.participant_id == p.participant_id, _A.account_type == "core")).first()
        if personal is None:
            continue
        pn = _frame(session, personal.account_id)
        cn = _frame(session, core.account_id if core else None)
        idx = pn.index.intersection(cn.index)
        if comparison == "common_period":
            pass  # intersected below across participants
        if len(idx) < 2:
            rows.append({"participant_id": p.participant_id, "display_name": p.display_name,
                         "weekly": None, "cumulative": None, "ir": None, "te": None,
                         "mdd": None, "_idx": idx})
            continue
        w = idx[-5:] if len(idx) >= 5 else idx
        weekly = float((pn.loc[w, "nav"].iloc[-1] / pn.loc[w, "nav"].iloc[0]) /
                       (cn.loc[w, "nav"].iloc[-1] / cn.loc[w, "nav"].iloc[0]) - 1.0)
        cumulative = float((pn.loc[idx, "nav"].iloc[-1] / pn.loc[idx, "nav"].iloc[0]) /
                           (cn.loc[idx, "nav"].iloc[-1] / cn.loc[idx, "nav"].iloc[0]) - 1.0)
        ti = tracking_ir(pn.loc[idx], cn.loc[idx])
        pm = perf_metrics(pn.loc[idx])
        rows.append({"participant_id": p.participant_id, "display_name": p.display_name,
                     "weekly": weekly, "cumulative": cumulative,
                     "ir": ti.get("information_ratio"), "te": ti.get("tracking_error"),
                     "mdd": pm.get("mdd"), "_idx": idx})
    if comparison == "common_period" and rows:
        common = None
        for r in rows:
            common = r["_idx"] if common is None else common.intersection(r["_idx"])
        if common is not None and len(common) >= 2:
            for r in rows:
                pn = _frame(session, _personal_id(session, r["participant_id"]))
                cn = _frame(session, _core_id(session, r["participant_id"]))
                r["cumulative"] = float(
                    (pn.loc[common, "nav"].iloc[-1] / pn.loc[common, "nav"].iloc[0]) /
                    (cn.loc[common, "nav"].iloc[-1] / cn.loc[common, "nav"].iloc[0]) - 1.0)
    key = {"active_return": "weekly", "cumulative": "cumulative", "ir": "ir", "mdd": "mdd"}[basis]
    if key == "mdd":
        # drawdown is negative-or-zero: best (closest to zero) first
        rows.sort(key=lambda r: (r[key] is None, -(r[key] or 0)))
    else:
        rows.sort(key=lambda r: (r[key] is None, -(r[key] or 0)))
    items = [{"rank": i + 1, "participant_id": r["participant_id"],
              "display_name": r["display_name"],
              "current_themes": theme_map.get(r["participant_id"], []),
              "active_return": r["weekly"] if basis == "active_return" else r[key],
              "cumulative": r["cumulative"], "mdd": r["mdd"], "te": r["te"]}
             for i, r in enumerate(rows)]
    return {"items": items, "period": period, "basis": basis, "comparison": comparison}


def _personal_id(session, pid: str):
    a = session.scalars(select(_A).where(_A.participant_id == pid,
                                         _A.account_type == "personal")).first()
    return a.account_id if a else None


def _core_id(session, pid: str):
    a = session.scalars(select(_A).where(_A.participant_id == pid,
                                         _A.account_type == "core")).first()
    return a.account_id if a else None

"""Copy only existing public market inputs into the isolated design workspace.

No accounts, NAV, holdings, transactions, credentials or sessions are read.
The existing Backend covariance and construction functions remain unchanged.
"""
import os
from pathlib import Path
import sqlite3

from sqlalchemy import select, insert
from ..db.models.price import PriceDaily
from ..db.models.operational import ForwardState
from .services import _common as C

MARKER = "design_price_reference_loaded"


def load_reference_prices(session):
    source = os.environ.get("DESIGN_PRICE_SOURCE", "").strip()
    if not source or session.get(ForwardState, MARKER):
        return
    path = Path(source).resolve()
    if not path.is_file():
        return
    # Never overwrite an existing workspace's market history implicitly.
    if session.scalar(select(PriceDaily.asset_id).limit(1)) is not None:
        return
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='prices_daily'").fetchone():
            return
        rows = connection.execute("SELECT asset_id, date, price, source FROM prices_daily ORDER BY asset_id, date").fetchall()
    if not rows:
        return
    from datetime import date
    # This is a market-data import, not a synthetic-price generator.
    session.execute(insert(PriceDaily), [dict(asset_id=a, date=date.fromisoformat(str(d)[:10]),
        price=p, source=origin) for a, d, p, origin in rows])
    session.add(ForwardState(key=MARKER, value="existing-v1-prices", updated_at=C.now_utc()))
    session.flush()

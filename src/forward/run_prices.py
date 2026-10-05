"""Collect completed observed prices without entering the trading/job engine.

This CLI opens only the explicit operating PostgreSQL target. It never initializes
schemas, jobs, events, orders, executions, holdings or NAV. The read-only path is
enforced by PostgreSQL from connection startup and does not fetch market data.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from src.data.closed_sessions import ClosedSessionProvider
from src.data.provider import NoPriceData
from src.forward.config import load_forward_config, resolve
from src.forward.frozen import load_frozen_benchmark
from src.forward.pg_adapter import Row, translate, to_psycopg_dsn

SOURCE = "yahoo-closed-session-v1"
USD_ASSETS = {"us_equity", "developed_ex_us", "emerging_markets", "gold", "global_reit"}
LOCK_ID = 734019512  # One price writer per operating database, across processes.


class PriceStore:
    """Small capability surface: fixed reads and append-only prices, no generic SQL."""

    def __init__(self, connection, *, postgres=False, read_only=False):
        self.connection = connection
        self.postgres = postgres
        self.read_only = read_only

    def _rows(self, sql, params=()):
        cursor = self.connection.execute(translate(sql) if self.postgres else sql, params)
        return [Row(dict(row)) for row in cursor.fetchall()]

    def coverage(self):
        return [dict(r) for r in self._rows(
            "SELECT asset_id, COUNT(*) AS rows, MIN(date) AS first, MAX(date) AS last "
            "FROM prices_daily GROUP BY asset_id ORDER BY asset_id")]

    def target(self):
        if not self.postgres:
            return {"backend": "sqlite-test"}
        database = self._rows("SELECT current_database() AS database")[0]["database"]
        revisions = sorted(row["version_num"] for row in self._rows(
            "SELECT version_num FROM alembic_version"))
        identity = f"{self.connection.info.host}/{database}"
        return {"backend": "postgres", "database": database, "schema_revisions": revisions,
                "fingerprint": hashlib.sha256(identity.encode()).hexdigest()[:16]}

    def boundary(self, requested):
        rows = self._rows("SELECT MIN(effective_date) AS first FROM portfolio_decisions")
        first = str(rows[0]["first"] or "")[:10]
        if not first:
            raise ValueError("No decision effective date; collection boundary is not established")
        return max(date.fromisoformat(requested), date.fromisoformat(first)).isoformat()

    def tickers(self, metadata):
        result = {("__FX__" if key == "FX_USDKRW" else key): value
                  for key, value in metadata.get("tickers", {}).items()}
        for row in self._rows("SELECT theme_id, ticker FROM themes WHERE active"):
            result["theme:" + row["theme_id"]] = row["ticker"]
        if "__FX__" not in result or len(result) < 2:
            raise ValueError("Missing core ticker or FX configuration")
        return result

    def existing(self, start):
        return {(r["asset_id"], str(r["date"])[:10]): (float(r["price"]), r["source"])
                for r in self._rows("SELECT asset_id, date, price, source FROM prices_daily "
                                    "WHERE date >= ?", (start,))}

    def append(self, rows):
        if self.read_only:
            raise PermissionError("Read-only price preflight cannot write")
        sql = ("INSERT INTO prices_daily (asset_id, date, price, source) VALUES (?, ?, ?, ?) "
               "ON CONFLICT (asset_id, date) DO NOTHING")
        total = 0
        for row in rows:
            cursor = self.connection.execute(translate(sql) if self.postgres else sql, row)
            total += cursor.rowcount
        return total


@contextmanager
def operating_store(*, read_only=False):
    """No fallback to auth DB/SQLite and no schema preparation on either path."""
    if os.environ.get("DATABASE_BACKEND") != "postgres":
        raise ValueError("Price CLI requires explicit DATABASE_BACKEND=postgres")
    url = os.environ.get("CAPSTONE_DESIGN_DATABASE_URL", "").strip()
    if not url.startswith(("postgresql://", "postgresql+psycopg://", "postgres://")):
        raise ValueError("Explicit PostgreSQL CAPSTONE_DESIGN_DATABASE_URL is required")
    import psycopg
    from psycopg.rows import dict_row

    # options applies before the first query, including metadata and boundary reads.
    options = "-c statement_timeout=30000 -c lock_timeout=5000"
    if read_only:
        options += " -c default_transaction_read_only=on"
    with psycopg.connect(to_psycopg_dsn(url), row_factory=dict_row,
                         connect_timeout=10, application_name="closed-price-collector",
                         options=options) as connection:
        if read_only:
            mode = connection.execute("SHOW transaction_read_only").fetchone()
            if mode["transaction_read_only"] != "on":
                raise RuntimeError("PostgreSQL did not enforce read-only mode")
        else:
            acquired = connection.execute("SELECT pg_try_advisory_xact_lock(%s) AS acquired",
                                          (LOCK_ID,)).fetchone()["acquired"]
            if not acquired:
                raise RuntimeError("Another price collector is running; retry later")
        yield PriceStore(connection, postgres=True, read_only=read_only)
        if read_only:
            connection.rollback()
        # A successful writer commits only appended prices on context exit.
        # Any exception rolls back the complete price batch.


def collect(store, tickers, *, start, now, source=None):
    """Retry missing dates from the forward boundary; never revise existing rows.

    Exact-date observed FX is required for USD assets. Empty holidays and still
    open sessions are normal. Source/parse errors are reported separately and
    cause CLI failure even when independently valid assets can be persisted.
    """
    if now.tzinfo is None:
        raise ValueError("An aware collection time is required")
    end = now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
    report = dict(start=start, asof=end, new_points=0, errors={}, empty=[],
                  pending={}, missing_fx={}, status="OK")
    if start > end:
        report["status"] = "NO_COMPLETED_DATA"
        return report
    provider = ClosedSessionProvider(source, now)
    observed = {}
    for asset, ticker in tickers.items():
        try:
            series = provider.get_price_history(ticker, start, end)
            series = series.loc[(series.index >= pd.Timestamp(start)) &
                                (series.index <= pd.Timestamp(end)) &
                                (series.index.dayofweek < 5)]
            if series.empty:
                report["empty"].append(asset)
            else:
                observed[asset] = series
        except NoPriceData:
            report["empty"].append(asset)
        except Exception as error:
            # Error messages may contain network URLs; retain only the class.
            report["errors"][asset] = type(error).__name__
    report["pending"] = {asset: provider.pending.get(ticker, 0)
                         for asset, ticker in tickers.items()}
    existing = store.existing(start)
    fx = observed.get("__FX__", pd.Series(dtype=float))
    rows = []
    for asset, series in observed.items():
        for timestamp, raw_price in series.items():
            day = timestamp.date().isoformat()
            if (asset, day) in existing:
                continue
            price = float(raw_price)
            if asset in USD_ASSETS or asset.startswith("theme:"):
                if timestamp not in fx.index:
                    report["missing_fx"].setdefault(asset, []).append(day)
                    continue
                price *= float(fx.loc[timestamp])
            if not math.isfinite(price) or price <= 0:
                raise ValueError("Invalid converted observed price")
            rows.append((asset, day, price, SOURCE))
    report["new_points"] = store.append(rows)
    if report["errors"]:
        report["status"] = "PARTIAL_FAILURE" if rows else "FAILED"
    elif not rows:
        report["status"] = "NO_NEW_COMPLETED_DATA"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, type=lambda value: date.fromisoformat(value).isoformat(),
                        help="Do not collect before this forward-operation boundary")
    parser.add_argument("--scheduled-for", type=lambda value: date.fromisoformat(value).isoformat(),
                        help="Audit label only; eligibility always uses actual current time")
    parser.add_argument("--dry-run", action="store_true", help="Database-enforced read-only preflight")
    parser.add_argument("--expected-database", help="Fail before collection if the database differs")
    parser.add_argument("--expected-revision", help="Fail before collection if the schema differs")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        cfg = load_forward_config()
        _, metadata = load_frozen_benchmark(resolve(cfg["frozen_dir"]))
        with operating_store(read_only=args.dry_run) as store:
            target = store.target()
            if args.expected_database and target.get("database") != args.expected_database:
                raise ValueError("Unexpected operating database")
            if args.expected_revision and target.get("schema_revisions") != [args.expected_revision]:
                raise ValueError("Unexpected operating schema revision")
            start = store.boundary(args.start)
            tickers = store.tickers(metadata)
            if args.dry_run:
                report = dict(status="READ_ONLY_PREFLIGHT", read_only=True, start=start,
                              coverage=store.coverage(), assets=sorted(tickers), new_points=0)
            else:
                report = collect(store, tickers, start=start, now=datetime.now(timezone.utc))
            report["scheduled_for"] = args.scheduled_for
            report["target"] = target
        code = int(bool(report.get("errors")))
    except Exception as error:
        # Keep credentials/connection URLs out of workflow logs and artifacts.
        report = dict(status="FAILED", error_type=type(error).__name__,
                      read_only=args.dry_run, new_points=0)
        code = 1
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        args.output.chmod(0o600)
    print(json.dumps(report, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

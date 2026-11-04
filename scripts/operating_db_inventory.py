"""Read-only inventory for comparing operating stores without credentials or PII."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from scripts.postgres_backup import BackupError, Connection

TABLES = (
    'users', 'sessions', 'participants', 'accounts', 'base_portfolio_selections',
    'portfolio_decisions', 'portfolio_choices', 'portfolio_targets', 'orders',
    'trades', 'holdings_daily', 'nav_daily', 'prices_daily', 'scheduled_jobs',
)
IDENTIFIERS = {
    'users': 'user_id', 'participants': 'participant_id', 'accounts': 'account_id',
    'portfolio_decisions': 'decision_id', 'portfolio_targets': 'target_id',
    'orders': 'order_id', 'trades': 'trade_id',
}


def inventory(url: str) -> dict:
    conn = Connection(url)
    # Enforce read-only at connection level, including metadata queries.
    conn.env['PGOPTIONS'] = conn.env.get('PGOPTIONS', '') + ' -c default_transaction_read_only=on'
    tables = set(json.loads(conn.query("SELECT coalesce(json_agg(table_name), '[]'::json) FROM information_schema.tables WHERE table_schema='public'")))
    fields = []
    for table in TABLES:
        if table not in tables:
            continue
        values = "'rows', count(*)"
        if table in IDENTIFIERS:
            column = IDENTIFIERS[table]
            values += f", 'id_fingerprints', coalesce(json_agg(md5({column}::text) ORDER BY {column}), '[]'::json)"
        fields += [f"'{table}', (SELECT json_build_object({values}) FROM {table})"]
    if 'alembic_version' in tables:
        fields += ["'alembic_revision', (SELECT json_agg(version_num) FROM alembic_version)"]
    if 'prices_daily' in tables:
        fields += ["'prices', (SELECT json_build_object('first',min(date),'last',max(date),'synthetic_rows',count(*) FILTER (WHERE source LIKE 'SYNTHETIC%')) FROM prices_daily)"]
    if 'nav_daily' in tables:
        fields += ["'valuations', (SELECT json_build_object('first',min(date),'last',max(date)) FROM nav_daily)"]
    if 'portfolio_decisions' in tables:
        fields += ["'decision_versions', (SELECT coalesce(json_agg(json_build_object('id_fingerprint',md5(decision_id),'user_fingerprint',md5(user_id),'version',version,'effective_date',effective_date) ORDER BY decision_id), '[]'::json) FROM portfolio_decisions)"]
    data = json.loads(conn.query('SELECT json_build_object(' + ','.join(fields) + ')'))
    return dict(identity=conn.identity(), inventory=data, read_only=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = {}
    failed = False
    for target, key in [('auth', 'DATABASE_URL'), ('design', 'CAPSTONE_DESIGN_DATABASE_URL')]:
        try:
            report[target] = inventory(os.environ.get(key, ''))
        except BackupError as error:
            report[target] = {'error': str(error)}
            failed = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    os.chmod(args.output, 0o600)
    print(json.dumps({target: {'read_only': data.get('read_only', False), 'error': data.get('error'), 'counts': {table: values['rows'] for table, values in data.get('inventory', {}).items() if isinstance(values, dict) and 'rows' in values}} for target, data in report.items()}))
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())

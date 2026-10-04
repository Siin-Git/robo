"""Exact NAV-path regression in a NEW disposable SYNTHETIC Monday fixture.

Reuses the existing launcher, accounts, clock and current/pending decisions.
Explicit NAV/holding test inputs are never created in an operating database.
"""
from datetime import date, datetime
import json

import start_monday_demo as monday

prepare_monday = monday.prepare


def prepare(directory, environment):
    prepare_monday(directory, environment)
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, select, delete
    from sqlalchemy.orm import Session
    from src.api.main import app
    from src.api.services import _common as C
    from src.db.models import Account, Holding, NavDaily

    accounts = json.loads((directory / 'accounts.json').read_text())['accounts']
    participants = {}
    with TestClient(app) as client:
        for index, confirmed_at in [(0, None), (2, '2026-10-01T03:00:00+00:00'),
                                    (3, '2026-09-30T03:00:00+00:00')]:
            client.cookies.clear()
            C.now_utc = lambda: datetime.fromisoformat(monday.MONDAY)
            account = accounts[index]
            assert client.post('/api/v1/auth/login', json={
                'email': account['email'], 'password': account['password']}).status_code == 200
            if confirmed_at:
                assert client.get('/api/v1/me/decisions').json()['items'] == []
                frontier = client.get('/api/v1/me/frontier').json()
                C.now_utc = lambda: datetime.fromisoformat(confirmed_at)
                response = client.post('/api/v1/me/onboarding/complete',
                    headers={'X-CSRF-Token': client.cookies['ra_csrf']},
                    json={'frontier_id': frontier['benchmark_frontier_id'], 'theme_ids': [],
                          'reason': 'SYNTHETIC observation-gap regression only'})
                assert response.status_code == 200
            C.now_utc = lambda: datetime.fromisoformat(monday.MONDAY)
            participants[index] = client.get('/api/v1/me').json()['participant_id']

    engine = create_engine('sqlite:///' + str(directory / 'portfolio_design.db'))
    with Session(engine) as session:
        for index, values in [
            (0, [('2026-10-01', 100), ('2026-10-02', 50), ('2026-10-05', 100)]),
            (3, [('2026-10-01', 100), ('2026-10-05', 101)]),
            (2, [('2026-10-05', 103)]),
        ]:
            for account in session.scalars(select(Account).where(
                    Account.participant_id == participants[index])):
                # This directory was freshly created by the guarded launcher.
                # Replace only its generated valuation inputs, never judgments.
                session.execute(delete(Holding).where(Holding.account_id == account.account_id))
                session.execute(delete(NavDaily).where(NavDaily.account_id == account.account_id))
                for day, level in values:
                    nav = (level if account.account_type == 'personal' else 100) * 1_000_000
                    session.add(NavDaily(account_id=account.account_id, date=date.fromisoformat(day),
                        nav=nav, nav_base100=level if account.account_type == 'personal' else 100,
                        daily_return=None, cumulative_return=0, cash_balance=0,
                        stale_price_flag=False, nav_status='OK', benchmark_version='CORE_V0.3',
                        theme_universe_version='THEME_UNIVERSE_V0.1',
                        risk_model_version='SYNTHETIC_TEST_NAV', execution_rule_version='SYNTHETIC_TEST_NAV'))
                    session.add(Holding(account_id=account.account_id, date=date.fromisoformat(day),
                        asset_id='us_equity', quantity=1, price=nav, market_value=nav, weight=1))
        session.commit()
    engine.dispose()
    (directory / 'ledger-observation-gap-fixture.json').write_text(json.dumps({
        'data_kind': 'TEST_FIXTURE', 'clock': monday.MONDAY,
        'participants': participants, 'a_index': 0, 'b_index': 3,
        'purpose': 'Explicit synthetic NAV regression inputs, not actual execution results'}, indent=2))


if __name__ == '__main__':
    monday.prepare = prepare
    monday.main()

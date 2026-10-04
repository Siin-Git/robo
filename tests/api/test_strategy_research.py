import pytest
from sqlalchemy import select, func
from src.db.models import PriceDaily, NavDaily, PortfolioDecision, Order
from src.api.services import strategy_service as svc
from src.strategies.sources import series_quality, excel_date, number, workbook
from .test_decisions import identity, confirm


def test_research_requires_login(client):
    assert client.get('/api/v1/strategies').status_code == 401
    assert client.get('/api/v1/strategies/leader_stock').status_code == 401


def test_catalog_does_not_choose_or_trade_variant(client, env, identity):
    cookies, headers = identity
    def counts():
        with env.factory() as s:
            return [s.scalar(select(func.count()).select_from(model)) for model in (PriceDaily, NavDaily, PortfolioDecision, Order)]
    before = counts()
    catalog = client.get('/api/v1/strategies', cookies=cookies).json()
    assert len(catalog['items']) == 2
    assert all(not s['active'] and not s['operational'] and not s['frontier_eligible'] and s['ticker'] is None for s in catalog['items'])
    detail = client.get('/api/v1/strategies/leader_stock', cookies=cookies).json()
    assert detail['report'] is None  # no default variant
    assert len(detail['variants']) == 3
    assert detail['snapshot']['as_of'] == '2026-10-01'
    assert sum(m['weight'] for m in detail['snapshot']['members']) == pytest.approx(1)
    assert detail['snapshot']['members'][-1]['ticker'] == 'A069500'
    assert detail['snapshot']['reconciliation']['independently_recalculated'] is False
    assert client.get('/api/v1/strategies/leader_stock?variant=export_historical', cookies=cookies).status_code == 404
    frontier = client.get('/api/v1/me/frontier', cookies=cookies).json()
    for tid in ['leader_stock', 'export_stock']:
        for route in ['preview', 'complete']:
            r = client.post('/api/v1/me/onboarding/' + route, cookies=cookies, headers=headers,
                json={'frontier_id': frontier['benchmark_frontier_id'], 'theme_ids': [tid]})
            assert r.status_code == 422, r.text
            assert r.json()['error']['code'] == 'STRATEGY_RESEARCH_ONLY'
    assert counts() == before
    # Existing ETF confirmation, immutable judgment and Frontier remain connected.
    result = confirm(client, identity)
    assert result.status_code == 200, result.text
    d = client.get('/api/v1/me/decisions', cookies=cookies).json()['items'][0]
    assert 'theme:ai' in d['weights'] and 'theme:leader_stock' not in d['weights']


@pytest.mark.parametrize('variant', ['leader_top10', 'leader_50_50', 'leader_regime'])
def test_monthly_history_is_not_daily_or_krw_nav(variant):
    detail = svc.detail('leader_stock', variant)
    report = detail['report']
    assert report['observations'] == len(report['series']) == 177
    assert report['frequency'] == 'MONTHLY'
    assert report['end'] == '2026-09-30'  # preserve supplied month label
    assert report['source_period']['end'] == '2026-09-29'
    assert report['date_semantics'] == 'MONTH_END_LABEL_NOT_EXECUTION_DATE'
    assert set(report['metrics']) == {'cumulative_return', 'mdd'}
    assert 'valuation' not in report and 'anchor' not in report
    assert not report['actual_account_history']
    assert report['quality']['interpolation'] == 'NONE'


@pytest.mark.parametrize('variant,last', [('export_historical', 9.390035887825022), ('export_conservative', 7.446207603953185)])
def test_export_daily_history_and_application_dates(variant, last):
    d = svc.detail('export_stock', variant)
    assert d['report']['observations'] == 1754
    assert d['report']['metrics']['cumulative_return'] == pytest.approx(last - 1)
    assert d['source_summary']['mdd'] == pytest.approx(d['report']['metrics']['mdd'])
    assert d['report']['end'] == '2026-09-23'
    assert d['snapshot']['signal_month'] == '2026-07'
    assert d['snapshot']['rebalance_date'] == '2026-09-01'
    assert d['snapshot']['snapshot_date'] == '2026-09-03'
    assert d['snapshot_applies_to_variant'] is False
    assert d['snapshot']['members'][0]['ticker'].startswith('0')
    assert d['snapshot_quality']['max_weight_reconciliation_error'] < 1e-10


@pytest.mark.parametrize('points,error', [
    ([{'date':'2026-01-02','level':100}, {'date':'2026-01-01','level':100}], 'SOURCE_DATES'),
    ([{'date':'2026-01-01','level':100}, {'date':'2026-01-01','level':100}], 'SOURCE_DATES'),
    ([{'date':'2026-01-01','level':0}], 'NON_POSITIVE'),
    ([{'date':'2026-01-01','level':100}, {'date':'2026-02-01','level':101,'return':.5}], 'SOURCE_RETURN')])
def test_reject_corrupt_sources(points, error):
    with pytest.raises(ValueError, match=error):
        series_quality(points, 'MONTHLY')


def test_source_units_and_dates():
    assert excel_date('46296') == '2026-10-01'
    with pytest.raises(ValueError, match='NON_FINITE'):
        number('nan')
    with pytest.raises(ValueError, match='SOURCE_DATE_SERIAL_INVALID'):
        excel_date('46296.5')


def test_import_rejects_different_excel_epoch(tmp_path):
    import zipfile
    path = tmp_path / 'different-epoch.xlsx'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><workbookPr date1904="1"/></workbook>')
    with pytest.raises(ValueError, match='UNSUPPORTED_EXCEL_DATE_SYSTEM'):
        workbook(path)

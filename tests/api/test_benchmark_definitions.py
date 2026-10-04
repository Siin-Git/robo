import pytest
from src.api.services.benchmark_definition_service import reference
from .test_decisions import identity


def report():
    return {'start':'2026-10-01','end':'2026-10-02','metrics':{'cumulative_return':.02}}


def config():
    return {'version':'TEST_ONLY','candidates':{},'definitions':{'safe_asset':{
        'id':'cash','label':'TEST_ONLY cash','currency':'KRW','dividends':'NONE','costs':'NONE',
        'method':'KRW_CASH_ZERO','approved':True,'approved_by':'TEST_FIXTURE','approved_at':'2026-10-01','version':'TEST_ONLY'}}}


def test_candidates_are_not_approved_and_require_login(client, identity):
    cookies, _ = identity
    cfg = client.get('/api/v1/benchmarks/definitions', cookies=cookies).json()
    assert cfg['definitions'] == {}
    assert {c['id'] for c in cfg['candidates']['market']} == {'kospi_price','kospi_total_return'}
    assert reference('market','market',report())['reason'] == 'BENCHMARK_DEFINITION_NOT_CONFIGURED'
    assert reference('safe_asset','cash',report())['return'] is None


def test_reviewed_cash_matches_period_but_cost_definition_difference_is_explicit():
    row = reference('safe_asset','cash',report(),config())
    assert row['status'] == 'AVAILABLE' and row['return'] == 0
    assert (row['start'],row['end']) == ('2026-10-01','2026-10-02')
    assert row['difference'] is None and row['difference_reason'] == 'REFERENCE_COST_OR_DIVIDEND_BASIS_DIFFERS'
    cfg = config();cfg['definitions']['safe_asset']['approved'] = False
    assert reference('safe_asset','cash',report(),cfg)['reason'] == 'BENCHMARK_DEFINITION_NOT_APPROVED'


@pytest.mark.parametrize('currency', ['USD','UNKNOWN'])
def test_no_silent_currency_conversion(currency):
    cfg = config();cfg['definitions']['safe_asset']['currency'] = currency
    assert reference('safe_asset','cash',report(),cfg)['reason'] == 'BENCHMARK_CURRENCY_DIFFERS'


def test_exact_endpoints_no_interpolation(tmp_path,monkeypatch):
    from src.api.services import benchmark_definition_service as service
    monkeypatch.setattr(service.C, 'ROOT', tmp_path)
    directory = tmp_path/'data/reference_benchmarks';directory.mkdir(parents=True)
    source = directory/'test.csv'
    source.write_text('date,level\n2026-10-01,100\n2026-10-02,103\n')
    cfg = config();d=cfg['definitions']['safe_asset'];d.update(method='SUPPLIED_LEVELS',data_file='data/reference_benchmarks/test.csv')
    row = reference('safe_asset','safe',report(),cfg)
    assert row['return'] == pytest.approx(.03)
    source.write_text('date,level\n2026-09-30,100\n2026-10-02,103\n')
    assert reference('safe_asset','safe',report(),cfg)['reason'] == 'SAME_PERIOD_PRICES_UNAVAILABLE'
    source.write_text('date,level\n2026-10-01,100\n2026-10-01,103\n')
    assert reference('safe_asset','safe',report(),cfg)['reason'] == 'BENCHMARK_DATES_NOT_UNIQUE_AND_ORDERED'
    source.write_text('date,level\n2026-10-01,100\n2026-10-02,inf\n')
    assert reference('safe_asset','safe',report(),cfg)['reason'] == 'BENCHMARK_LEVELS_INVALID'


def test_matching_reviewed_net_levels_allow_difference(tmp_path,monkeypatch):
    # Synthetic reviewed net reference only, never a real benchmark approval.
    from src.api.services import benchmark_definition_service as service
    monkeypatch.setattr(service.C, 'ROOT', tmp_path)
    directory = tmp_path/'data/reference_benchmarks';directory.mkdir(parents=True)
    (directory/'net-test.csv').write_text('date,level\n2026-10-01,100\n2026-10-02,103\n')
    cfg = config()
    cfg['definitions']['safe_asset'].update(method='SUPPLIED_LEVELS',
        data_file='data/reference_benchmarks/net-test.csv',
        costs='TRANSACTION_COSTS_INCLUDED',dividends='PROVIDER_ADJUSTED_OR_CLOSE')
    row = reference('safe_asset','safe',report(),cfg)
    assert row['status'] == 'AVAILABLE'
    assert row['difference'] == pytest.approx(-.01)
    assert row['difference_reason'] is None

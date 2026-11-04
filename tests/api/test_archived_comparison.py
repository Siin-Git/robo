"""Saved cohort ranking must neither mutate live ledgers nor expose peer balances."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import pytest
from sqlalchemy import select, func
from src.db.models import Event, NavDaily, Trade
from src.api.services.archived_comparison_service import archive_report
from .test_ledger_comparison import confirmed, get_comparison


def archive(decision, value):
    return {'kind':'HISTORICAL_REPLAY','run_id':'test-run','source_sha256':'test-source',
        'start':'2026-08-31','end':'2026-10-06','selection_basis':'CURRENT_CONFIRMED_CONFIGURATION',
        'execution_basis':'INITIAL_BUY_AND_HOLD','cost_bps':5,'decision_id':decision['decision_id'],
        'series':[{'date':d,'personal_nav':v,'core_nav':b} for d,v,b in
                  [('2026-08-31',100,100),('2026-10-02',100,101),('2026-10-06',value,102)]],
        'ledger':{'snapshots':[{'date':d,'nav':v,'cash_balance':0,'nav_status':'OK',
                    'holdings':[{'asset_id':'theme:ai','market_value':v,'price':v,'quantity':1}]} for d,v in
                    [('2026-08-31',100),('2026-10-02',100),('2026-10-06',value)]],
                  'trades':[]}}


def test_saved_comparison_uses_common_archive_and_preserves_live_ledger(client, env, monkeypatch):
    a, da = confirmed(client, monkeypatch, 'archive-a@example.com')
    _, db = confirmed(client, monkeypatch, 'archive-b@example.com')
    payloads=[archive(da,110),archive(db,120)]
    with env.factory() as s:
        for i,(decision,payload) in enumerate(zip([da,db],payloads)):
            s.add(Event(event_id=f'saved{i}',event_type='HISTORICAL_REPLAY_ARCHIVED',
                participant_id=decision['participant_id'],account_id=decision['account_id'],
                timestamp=datetime.now(timezone.utc),model_version='test',payload_json=payload))
        s.commit()
        before=s.scalar(select(func.count()).select_from(NavDaily)),s.scalar(select(func.count()).select_from(Trade))
    assert get_comparison(client,a)['ranked']==0
    result=get_comparison(client,a,'?source=auto&period=1M')
    assert result['selected_source']=='archive'
    assert result['ranked']==2 and result['start']=='2026-10-02'
    rows={r['participant_id']:r for r in result['items']}
    assert rows[da['participant_id']]['rank']==2
    assert rows[db['participant_id']]['rank']==1
    assert rows[da['participant_id']]['metrics']['cumulative_return']==pytest.approx(.1)
    assert rows[da['participant_id']]['metrics']['benchmark_return']==pytest.approx(102/101-1)
    assert rows[da['participant_id']]['metrics']['difference_pp']==pytest.approx(.1-(102/101-1))
    assert rows[db['participant_id']]['series'][-1]['personal_index100']==pytest.approx(120)
    assert rows[db['participant_id']]['metrics']['volatility'] is None
    assert result['theme_selectors'][0]['count']==2
    public=json.dumps(result)
    for forbidden in ['account_id','decision_id','cash_balance','personal_nav','quantity','holdings','orders','trades']:
        assert forbidden not in public
    assert get_comparison(client,a,'?source=forward')['ranked']==0
    risk=get_comparison(client,a,'?source=archive&basis=volatility')
    assert risk['ranked']==0 and risk['return_ranked']==2
    assert client.get('/api/v1/me/performance/comparison?source=invalid',cookies=a).status_code==400
    with env.factory() as s:
        assert before==(s.scalar(select(func.count()).select_from(NavDaily)),s.scalar(select(func.count()).select_from(Trade)))
        assert s.get(Event,'saved0').payload_json==payloads[0]
        # A later archive from a different run must never be mixed into this cohort.
        other=deepcopy(payloads[1]);other['run_id']='different-run'
        s.add(Event(event_id='other',event_type='HISTORICAL_REPLAY_ARCHIVED',participant_id=db['participant_id'],
            account_id=db['account_id'],timestamp=datetime.now(timezone.utc),model_version='test',payload_json=other));s.commit()
    assert get_comparison(client,a,'?source=archive')['ranked']==0


def test_adapter_retains_interior_drawdown_and_missing_core():
    saved=archive({'decision_id':'d'},120)
    saved['ledger']['snapshots'][1]['nav']=50
    saved['ledger']['snapshots'][1]['holdings'][0].update(market_value=50,price=50)
    saved['series'][-1]['core_nav']=None
    result=archive_report(saved,'ALL')
    assert result['metrics']['mdd']==-.5
    assert result['metrics']['benchmark_return'] is None
    assert result['metrics']['difference_pp'] is None
    assert result['metrics']['volatility'] is None

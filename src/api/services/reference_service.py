"""Same-period benchmark evidence, never substituted for actual holdings."""
import pandas as pd
from sqlalchemy import select
from ...db.models import PriceDaily, Account
from ...forward.reference_portfolio import evaluate_levels
from . import _common as C
from .decision_service import latest

def comparisons(session, participant_id, report):
    start,end=report['start'],report['end']
    core={'key':'core','label':'시스템 기준 CORE','status':'AVAILABLE' if report['metrics']['benchmark_return'] is not None else 'UNAVAILABLE',
        'return':report['metrics']['benchmark_return'],'reason':None if report['metrics']['benchmark_return'] is not None else 'SAME_PERIOD_LEDGER_MISSING',
        'source':'ACCOUNT_LEDGER','start':start,'end':end}
    personal=session.scalar(select(Account).where(Account.participant_id==participant_id,Account.account_type=='personal'))
    decision=latest(session,personal.account_id) if personal else None
    # No project-wide market or safe-asset benchmark definition is frozen.
    # US equity and Treasuries cannot silently stand in for those definitions.
    rows=[core]
    selected={'key':'selected_base','label':'사용자 선택 기본 구성 · 매수 후 보유 가격 비교','status':'UNAVAILABLE','return':None,
              'source':'REFERENCE_PRICE_REPLAY_GROSS','actual_account_history':False,'costs_included':False,'start':start,'end':end,'reason':'NO_CONFIRMED_BASE_SNAPSHOT'}
    if decision and start and end and start<end:
        prices=list(session.scalars(select(PriceDaily).where(PriceDaily.date>=C.as_date(start),PriceDaily.date<=C.as_date(end))))
        frame=pd.DataFrame([{'date':p.date,'asset':p.asset_id,'price':float(p.price)} for p in prices])
        try:
            if frame.empty:
                raise ValueError('SAME_PERIOD_PRICES_UNAVAILABLE')
            levels=frame.pivot(index='date',columns='asset',values='price');levels.index=pd.to_datetime(levels.index)
            nav=evaluate_levels(decision.provenance_json['base_weights'],levels,start,end)
            selected.update(status='AVAILABLE',reason=None)
            selected['return']=float(nav.nav.iloc[-1]/nav.nav.iloc[0]-1)
        except ValueError as exc:
            selected['reason']=str(exc)
    elif decision:
        selected['reason']='INSUFFICIENT_ACTUAL_HISTORY'
    rows.append(selected)
    for key,label in [('market','시장 비교'),('safe_asset','안전자산 비교')]:
        rows.append({'key':key,'label':label,'status':'UNAVAILABLE','return':None,'reason':'BENCHMARK_DEFINITION_NOT_CONFIGURED','start':start,'end':end})
    return rows

"""Read-only owner projection of one stored asset; never a trading recommendation."""
from copy import deepcopy
from .decision_service import own
from .internal_tracking_service import report
from .decision_verification_service import _number


def case(session, user_id, decision_id):
    decision = own(session, user_id, decision_id)  # Before any internal diagnostics read.
    observed = report(session, decision_id)
    assets = [a for a in observed['assets'] if a['asset_id'] != 'cash'
              and (_number(a['confirmed_weight']) or 0) > 0]
    if not assets:
        return {'available': False, 'decision_id': decision_id, 'reason': 'NO_INVESTED_ASSET',
                'message': '검토할 편입 자산이 없습니다.', 'read_only': True}
    def saved(a):
        e = a.get('initial_estimate') or {}
        return _number(e.get('expected_return')) is not None and _number(e.get('volatility')) is not None
    # Prefer a recorded original estimate and an independently modelled base asset.
    # Stable selection by stored weight, never by observed performance.
    asset = sorted(assets, key=lambda a: (not saved(a), a['asset_id'].startswith('theme:'),
                                         -a['confirmed_weight'], a['asset_id']))[0]
    estimate = asset.get('initial_estimate') or {}
    allowed_estimate = {k: deepcopy(estimate.get(k)) for k in (
        'expected_return', 'volatility', 'unit', 'horizon', 'return_basis',
        'risk_basis', 'independent_theme_forecast')} if estimate else None
    curve = asset['price_curve']
    forbidden = lambda source: not source or any(v in source.lower() for v in ('synthetic', 'fixture', 'replay', 'test'))
    excluded = observed['data_kind'] == 'TEST_FIXTURE' or any(
        p['price'] is not None and forbidden(p.get('source')) for p in curve)
    rows = [dict(p) for p in curve if p['price'] is not None] if not excluded else []
    reasons = []
    if not saved(asset):
        reasons.append({'code': 'INITIAL_ESTIMATE_MISSING', 'text': '확정 당시 자산별 예상이 충분히 저장되지 않아 최초 판단과 대조할 수 없습니다.'})
    if excluded:
        reasons.append({'code': 'SOURCE_NOT_ELIGIBLE', 'text': '시험·재생 자료 또는 출처 미확인 가격은 실제 관측 근거에서 제외했습니다.'})
    if len(rows) < 2:
        reasons.append({'code': 'INSUFFICIENT_OBSERVATIONS', 'text': '판단 효력일 이후 유효한 가격 관측이 두 날짜 미만이라 기간 변화율을 계산할 수 없습니다.'})
    elif any(h['status'] != 'REACHED' for h in asset['horizons']):
        reasons.append({'code': 'HORIZON_NOT_REACHED', 'text': '판단 이후 3·6개월 관측 기간이 아직 충족되지 않았습니다.'})
    if asset['missing_price_dates'] or asset['invalid_price_dates']:
        reasons.append({'code': 'PRICE_GAPS', 'text': '관측 구간에 누락되거나 유효하지 않은 가격이 있습니다.'})
    if estimate.get('independent_theme_forecast') is False:
        reasons.append({'code': 'THEME_NOT_INDEPENDENT', 'text': '저장된 테마 예상은 독립적인 테마 예측값이 아닙니다.'})
    reasons.append({'code': 'COMPARISON_DEFINITION_PENDING', 'text': '연간 예상과 관측 결과를 어떤 기간·기준으로 대조할지 합의되지 않아 적중 여부와 Revision 판단을 보류합니다.'})
    return {'available': True, 'decision_id': decision_id, 'decision_version': decision.version,
            'asset_id': asset['asset_id'], 'confirmed_weight': asset['confirmed_weight'],
            'selection_reason': '최초 예상 보유 여부, 기본 자산 여부, 확정 비중 순으로 선정했습니다. 사후 수익률로 고르지 않았습니다.',
            'initial_estimate': allowed_estimate, 'initial_estimate_status': asset['initial_estimate_status'],
            'window_start': observed['window_start'], 'window_end_exclusive': observed['window_end_exclusive'],
            'window_status': observed['window_status'], 'as_of': observed['as_of'],
            'observation': {'count': len(rows), 'start': rows[0]['date'] if rows else None,
                'end': rows[-1]['date'] if rows else None, 'first_price': rows[0]['price'] if rows else None,
                'last_price': rows[-1]['price'] if rows else None,
                'price_return': asset['cumulative_price_return'] if len(rows) >= 2 else None,
                'basis': asset['price_basis'], 'curve': [] if excluded else curve,
                'missing_dates': asset['missing_price_dates'], 'invalid_dates': asset['invalid_price_dates'],
                'sources': sorted({p['source'] for p in rows if p.get('source')}),
                'excluded': excluded},
            'horizons': [dict(h, status='UNVERIFIED', cumulative_price_return=None) if excluded else h for h in asset['horizons']],
            'assessment': {'action': 'DEFER', 'label': 'Revision 판단 보류',
                'kind': 'DATA_SUFFICIENCY_CHECK', 'reasons': reasons,
                'next_step': '원래 예상을 만든 담당 팀과 비교 기준을 정하고, 필요한 기간의 관측을 확보한 뒤 유지·수정 여부를 검토합니다.',
                'recorded_human_review': False},
            'data_kind': observed['data_kind'], 'historical_replay_excluded': True,
            'read_only': True, 'changes_model_or_orders': False}

"""Read-only financial/data audit against the running demo (auth sessions only mutate)."""
from __future__ import annotations
import json
import math
import os
import statistics
import sys
from pathlib import Path
import httpx
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.local.capstone import COHORT, COHORT_SIZE, EMAILS, PASSWORD


def independently_calculate(series):
    nav = [p['personalized_nav'] for p in series]
    core = [p['core_nav'] for p in series]
    returns = [b/a-1 for a,b in zip(nav, nav[1:])]
    sd = statistics.stdev(returns)
    high, mdd = nav[0], 0.
    for value in nav:
        high = max(high, value)
        mdd = min(mdd, value/high-1)
    ret, cr = nav[-1]/nav[0]-1, core[-1]/core[0]-1
    return dict(nav=nav[-1], cumulative_return=ret, core_return=cr, excess_return=ret-cr,
                mdd=mdd, volatility=sd*math.sqrt(252), sharpe=statistics.mean(returns)/sd*math.sqrt(252))


def main():
    output = Path(os.environ.get('CAPSTONE_AUDIT_PATH', str(ROOT / '.work/capstone_audit.json')))
    frozen = json.loads((ROOT/'outputs/frozen/CORE_V0.3/weights.json').read_text())
    reports, accounts, errors = [], [], {}
    with httpx.Client(base_url=os.environ.get('CAPSTONE_BASE_URL', 'http://127.0.0.1:3001'),timeout=60) as c:
        for email,(name,themes) in zip(EMAILS,COHORT):
            assert c.get('/api/v1/me/comparison').status_code == 401
            login = c.post('/api/v1/auth/login',json=dict(email=email,password=PASSWORD))
            assert login.status_code == 200, email
            pid = login.json()['user']['participant_id']
            me = c.get('/api/v1/auth/me').json()
            r = c.get('/api/v1/me/comparison').json()
            assert me['participant_id'] == pid == r['participant_id']
            assert r['display_name'] == name and r['themes'] == themes and len(set(themes)) <= 2
            assert c.get(f'/api/v1/participants/{pid}/comparison').json() == r
            series = r['series']; dates = [p['date'] for p in series]
            assert len(dates) == len(set(dates)) == r['observations'] == 118
            assert dates == sorted(dates) and dates[0] == r['start'] and dates[-1] == r['end']
            for key in ['personalized_nav','core_nav']:
                assert series[0][key] == 100
                assert all(isinstance(p[key],(float,int)) and math.isfinite(p[key]) and p[key]>0 for p in series)
            assert {w['asset_id']:w['weight'] for w in r['core_allocation']} == frozen
            for allocation in [r['allocation'],r['core_allocation']]:
                assert len({w['asset_id'] for w in allocation}) == len(allocation)
                assert all(math.isfinite(w['weight']) and 0<=w['weight']<=1 for w in allocation)
                assert abs(sum(w['weight'] for w in allocation)-1)<1e-12
            actual_themes = {w['asset_id']:w['weight'] for w in r['allocation'] if w['asset_type']=='theme'}
            assert actual_themes == {t:.075 for t in themes}
            calculated = independently_calculate(series)
            for key,value in calculated.items():
                delta = abs(r['metrics'][key]-value)
                errors[key] = max(errors.get(key,0),delta)
                assert math.isfinite(r['metrics'][key]) and delta < 1e-12,(email,key,delta)
            if reports:
                assert r['core_allocation'] == reports[0]['core_allocation']
                assert dates == [p['date'] for p in reports[0]['series']]
                assert [p['core_nav'] for p in series] == [p['core_nav'] for p in reports[0]['series']]
                assert r['metrics']['core_return'] == reports[0]['metrics']['core_return']
            r['independent_metrics'] = calculated
            reports.append(r)
            cookie = c.cookies['ra_session']; csrf=c.cookies['ra_csrf']
            assert c.post('/api/v1/auth/logout',headers={'X-CSRF-Token':csrf}).status_code == 200
            assert not c.cookies.get('ra_session') and not c.cookies.get('ra_csrf')
            assert c.get('/api/v1/auth/me').status_code == 401
            assert c.get('/api/v1/auth/me',headers={'Cookie':f'ra_session={cookie}'}).status_code == 401
            accounts.append(dict(email=email,participant_id=pid,themes=themes,result='PASS'))
        assert len({r['participant_id'] for r in reports}) == COHORT_SIZE
        assert c.post('/api/v1/auth/login',json=dict(email=EMAILS[0],password=PASSWORD)).status_code == 200
        rankings = {}
        for basis,key in dict(return_='cumulative_return',excess='excess_return',mdd='mdd',volatility='volatility',sharpe='sharpe').items():
            basis = basis.removesuffix('_')
            response = c.get('/api/v1/comparison/rankings',params={'basis':basis})
            assert response.status_code == 200
            rows = response.json()['items']
            active_reports = []
            for row in rows:
                report = next((r for r in reports if r['participant_id']==row['participant_id']), None)
                if report is None:
                    report = c.get(f"/api/v1/participants/{row['participant_id']}/comparison").json()
                    report['independent_metrics'] = independently_calculate(report['series'])
                active_reports.append(report)
            assert len(rows) == response.json()['total'] <= response.json()['registered'] <= COHORT_SIZE
            expected = sorted(active_reports,key=lambda r:((1 if basis=='volatility' else -1)*r['independent_metrics'][key],r['participant_id']))
            assert [r['participant_id'] for r in rows] == [r['participant_id'] for r in expected]
            expected_ranks, previous, rank = [], None, 0
            for i, r in enumerate(expected, 1):
                value = r['metrics'][key]
                if previous is None or value != previous:
                    rank = i
                expected_ranks.append(rank)
                previous = value
            assert [r['rank'] for r in rows] == expected_ranks
            for row in rows:
                original=next(r for r in active_reports if r['participant_id']==row['participant_id'])
                assert row['metrics']==original['metrics'] and row['themes']==original['themes']
            rankings[basis] = rows
        assert c.get('/api/v1/participants/unknown/comparison').status_code == 404
        other = reports[1]['participant_id']
        assert c.get(f'/api/v1/participants/{other}/performance').status_code == 403
        assert c.post('/api/v1/auth/logout',headers={'X-CSRF-Token':c.cookies['ra_csrf']}).status_code == 200
    result=dict(result='PASS',accounts=accounts,reports=reports,rankings=rankings,max_errors=errors,
                period=[reports[0]['start'],reports[0]['end']],observations=118,daily_returns=117)
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(f'{COHORT_SIZE}/{COHORT_SIZE} accounts PASS; NAV/core/themes/allocations/formulas/rankings/session revocation PASS')
    print('Maximum formula errors:',errors)
    print('Top 3:',{k:[r['display_name'] for r in v[:3]] for k,v in rankings.items()})
    print(output)

if __name__=='__main__': main()

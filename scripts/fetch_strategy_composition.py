import sys,json,re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.api.services.strategy_service import bundle
from src.data.provider import YahooChartProvider
_,d=bundle()
leader=d['snapshots']['leader_measurement'];export=d['snapshots']['export_historical']['items'][-1]
models=[{'id':'leader_stock','label':'주도주 모델','as_of':leader['as_of'],'source':leader['source'],'members':[{'ticker':m['ticker'].removeprefix('A'),'company':m['company'],'weight':m['weight']} for m in leader['members']]}, {'id':'export_stock','label':'수출주 모델','as_of':export['snapshot_date'],'source':d['snapshots']['export_historical']['source'],'members':[{'ticker':m['ticker'],'company':m['company'],'weight':m['actual_weight']} for m in export['members'] if m['actual_weight']>0]+[{'ticker':'cash','company':'현금','weight':export['cash_weight']}]}]
tickers=sorted({m['ticker'] for model in models for m in model['members'] if m['ticker']!='cash'})
# Yahoo returns only observed bars; try the two Korean listing venues, never a proxy.
def fetch(t):
    failures=[]
    for suffix in ['KS','KQ']:
        try:
            s=YahooChartProvider().get_price_history(t+'.'+suffix,'2021-09-01','2026-09-11')
            if s.attrs['session_timezone']!='Asia/Seoul': raise ValueError('WRONG_MARKET')
            return t,{'symbol':t+'.'+suffix,'session_timezone':s.attrs['session_timezone'],'prices':{str(i.date()):float(v) for i,v in s.items()}}
        except Exception as e: failures.append(type(e).__name__)
    raise ValueError(t+':'+','.join(failures))
with ThreadPoolExecutor(max_workers=5) as pool: prices=dict(pool.map(fetch,tickers))
out={'version':'STRATEGY_COMPOSITION_20261013','retrieved_at':datetime.now(timezone.utc).isoformat(),'price_basis':'YAHOO_ADJUSTED_CLOSE_EXCHANGE_SESSION','requested_period':{'start':'2021-09-01','end':'2026-09-11'},'models':models,'prices':prices,'sources':d['sources']}
p=ROOT/'data/strategy_research/composition_prices_20261013.json';p.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')))
print(json.dumps({'symbols':len(prices),'bytes':p.stat().st_size,'models':[{ 'id':m['id'],'members':len(m['members']),'weight_sum':sum(x['weight'] for x in m['members'])} for m in models]},ensure_ascii=False))

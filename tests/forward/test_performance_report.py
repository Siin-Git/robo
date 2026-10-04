import math
import pandas as pd
import pytest
from src.forward.performance_report import calculate_report


def ledger():
    dates = ["2026-09-07", "2026-09-08", "2026-09-09"]
    nav = [{"date":d,"nav":v,"cash":cash} for d,v,cash in zip(dates,[100,102,105.05],[0,-1,-1])]
    bench = [{"date":d,"nav":v} for d,v in zip(dates,[100,101,102])]
    holds = []
    for d,values in zip(dates,[{"us_equity":60,"us_treasury":40},{"us_equity":42,"us_treasury":40,"theme:ai":21},{"us_equity":44,"us_treasury":40,"theme:ai":22.05}]):
        for a,v in values.items():
            holds.append({"date":d,"asset_id":a,"market_value":v,"price":v})
    trades = [{"date":dates[1],"asset_id":"us_equity","quantity":-1,"gross_value":21,"cost":.5},
              {"date":dates[1],"asset_id":"theme:ai","quantity":1,"gross_value":21,"cost":.5}]
    return nav,bench,holds,trades


def test_rebalance_costs_and_compound_reconcile_every_date():
    report = calculate_report(*ledger())
    assets = {r["asset_id"]:r for r in report["assets"]}
    assert assets["us_equity"]["contribution"] == pytest.approx(.05)
    assert assets["theme:ai"]["contribution"] == pytest.approx(.0105)
    assert assets["costs"]["contribution"] == pytest.approx(-.01)
    assert assets["unexplained"]["contribution"] == pytest.approx(0,abs=1e-12)
    assert assets["theme:ai"]["price_return"] is None
    assert report["metrics"]["difference_pp"] == pytest.approx(.0305)
    assert report["metrics"]["volatility"] is None
    for point in report["attribution"]:
        assert sum(point["values"].values()) == pytest.approx(point["total"],abs=1e-12)


def test_missing_holdings_is_unexplained_not_fake_asset_profit():
    nav,bm,holds,trades = ledger()
    holds = [h for h in holds if h["date"] != nav[1]["date"]]
    report = calculate_report(nav,bm,holds,trades)
    assert report["quality"]["unresolved_intervals"] == 2
    assets = {r["asset_id"]:r for r in report["assets"]}
    assert assets["us_equity"]["contribution"] == 0
    assert assets["us_equity"]["average_weight"] is None
    assert assets["unexplained"]["contribution"] == pytest.approx(.0605)
    assert sum(r["contribution"] for r in report["assets"]) == pytest.approx(.0505)


def test_missing_benchmark_endpoint_does_not_compare_other_dates():
    nav,bm,holds,trades = ledger()
    report = calculate_report(nav,bm[1:],holds,trades)
    assert report["metrics"]["benchmark_return"] is None
    assert report["metrics"]["difference_pp"] is None
    assert all(r["benchmark"] is None for r in report["series"])


def test_period_rebases_every_metric_and_contribution():
    dates = pd.bdate_range("2026-06-01","2026-09-11")
    nav = [{"date":d.date().isoformat(),"nav":100*1.001**i,"cash":0} for i,d in enumerate(dates)]
    holds = [{"date":n["date"],"asset_id":"us_equity","market_value":n["nav"],"price":n["nav"]} for n in nav]
    full = calculate_report(nav,nav,holds,[])
    month = calculate_report(nav,nav,holds,[],"1M")
    assert month["start"] == "2026-08-11"
    assert month["series"][0]["personal"] == 0
    assert month["attribution"][0]["total"] == 0
    assert month["metrics"]["cumulative_return"] < full["metrics"]["cumulative_return"]
    assert sum(a["contribution"] for a in month["assets"]) == pytest.approx(month["metrics"]["cumulative_return"])
    assert month["metrics"]["volatility"] is None
    assert full["metrics"]["volatility"] is not None
    assert full["metrics"]["information_ratio"] is None  # zero active risk


@pytest.mark.parametrize("nav",[[],[{"date":"2026-09-11","nav":100,"cash":100}]])
def test_no_invented_zero_performance_before_second_observation(nav):
    report = calculate_report(nav,[],[],[])
    assert report["metrics"]["cumulative_return"] is None
    assert report["series"] == []


def test_stale_prices_and_gaps_suppress_annual_risk():
    dates = pd.bdate_range("2026-06-01","2026-09-11")
    nav = [{"date":d.date().isoformat(),"nav":100+i,"cash":100+i} for i,d in enumerate(dates)]
    nav[4]["status"] = "STALE_PRICE"
    del nav[8]
    report = calculate_report(nav,nav,[],[])
    assert report["metrics"]["volatility"] is None
    assert report["metrics"]["tracking_error"] is None
    assert report["quality"]["stale_observations"] == 1
    assert report["quality"]["missing_nav_dates"] == 1


def test_invalid_period():
    with pytest.raises(ValueError):
        calculate_report([],[],[],[],"NOPE")


def test_single_anchor_excludes_incomplete_latest_record_without_fake_performance():
    nav=[{'date':'2026-10-05','nav':123456,'cash':456,'status':'OK'},
         {'date':'2026-10-06','nav':0,'cash':456,'status':'NAV_INCOMPLETE'}]
    report=calculate_report(nav,[],[],[])
    assert report['observations']==1
    assert report['valuation']=={'date':'2026-10-05','nav_krw':123456,'cash_krw':456,'index100':100}
    assert report['end']=='2026-10-05'
    assert report['latest_recorded_date']=='2026-10-06'
    assert report['latest_recorded_status']=='NAV_INCOMPLETE'
    assert report['series']==[]
    assert all(v is None for v in report['metrics'].values())

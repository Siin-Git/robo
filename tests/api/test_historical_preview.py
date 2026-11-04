from datetime import date, datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.db.base import Base
from src.db.models import Account, Event, Participant, User, BasePortfolioSelection, PortfolioTarget
from src.db.models.decision import PortfolioDecision
from src.api.services.historical_preview_service import own, EVENT_TYPE


def test_archive_ownership_no_cross_account_and_not_live_nav(tmp_path):
    engine=create_engine(f'sqlite:///{tmp_path / "preview.db"}');Base.metadata.create_all(engine)
    stamp=datetime.now(timezone.utc)
    with Session(engine) as db:
        for n in (1,2):
            db.add(Participant(participant_id=f'P{n}',display_name=f'P{n}',status='active',join_date=date(2026,10,2),created_at=stamp,updated_at=stamp));db.flush()
            db.add(User(user_id=f'U{n}',participant_id=f'P{n}',email=f'test{n}@example.com',email_normalized=f'test{n}@example.com',password_hash='test-only',role='user',status='active',created_at=stamp,updated_at=stamp));db.flush()
            db.add(Account(account_id=f'A{n}',participant_id=f'P{n}',account_type='personal',benchmark_version='core',inception_date=date(2026,10,2),initial_capital_krw=100,status='active',created_at=stamp));db.flush()
            db.add(BasePortfolioSelection(selection_id=f'S{n}',user_id=f'U{n}',participant_id=f'P{n}',frontier_version='v1',frontier_id='f1',weights_json={'cash':1},selected_at=stamp,effective_at=stamp,status='active'))
            db.add(PortfolioTarget(target_id=f'T{n}',account_id=f'A{n}',effective_date=date(2026,10,6),kind='test',weights_json={'cash':1},core_version='core',theme_universe_version='v1',risk_model_version='v1',created_at=stamp));db.flush()
            db.add(PortfolioDecision(decision_id=f'D{n}',user_id=f'U{n}',participant_id=f'P{n}',account_id=f'A{n}',version=1,selection_id=f'S{n}',target_id=f'T{n}',confirmed_at=stamp,effective_date=date(2026,10,6),weights_json={'cash':1},expectations_json={},provenance_json={}))
        db.commit()
        assert own(db,'P1','U1')=={'available':False}
        payload={'kind':'HISTORICAL_REPLAY','decision_id':'D1','series':[{'date':'2026-10-02','personal_index':100}],'summary':{'personal_return':0}}
        db.add(Event(event_id='archive1',event_type=EVENT_TYPE,participant_id='P1',account_id='A1',timestamp=stamp,model_version='v1',payload_json=payload));db.commit()
        assert own(db,'P1','U1')['report']['is_current_configuration'] is True
        assert own(db,'P2','U2')=={'available':False}
        assert own(db,'P1','U2')=={'available':False}
        # A malformed event bound to another person's saved decision is ignored.
        db.add(Event(event_id='archive2',event_type=EVENT_TYPE,participant_id='P2',account_id='A2',timestamp=stamp,model_version='v1',payload_json=payload));db.commit()
        assert own(db,'P2','U2')=={'available':False}
        db.add(PortfolioDecision(decision_id='D3',user_id='U1',participant_id='P1',account_id='A1',version=2,selection_id='S1',target_id='T1',confirmed_at=stamp,effective_date=date(2026,10,13),weights_json={'cash':1},expectations_json={},provenance_json={}));db.commit()
        result=own(db,'P1','U1');assert result['report']['is_current_configuration'] is False
        from sqlalchemy import text
        assert db.scalar(text('SELECT count(*) FROM nav_daily'))==0
        assert db.scalar(text('SELECT count(*) FROM trades'))==0
        assert db.get(Event,'archive1').payload_json==payload


def test_history_endpoint_requires_login(client):
    assert client.get('/api/v1/me/performance/history').status_code==401

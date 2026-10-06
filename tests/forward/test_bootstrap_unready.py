"""Professor setup in disposable auth/design stores, never operating secrets."""
from hashlib import sha256
import json

import pytest
from sqlalchemy import select, delete

from tests.forward.test_competition_start import build
from scripts import bootstrap_unready_portfolios as bootstrap
from src.db.base import Base
from src.db.models import Theme, PortfolioDecision, Participant, User, Account, PortfolioTarget, Event, View
from src.db.models.demo_cohort import DemoSlot, DemoCohort
from src.db.models.onboarding import OnboardingDraft
from src.api.services import onboarding_service, _common as C


def prepared(build):
    x = build(15)
    ids = ('ai', 'robotics', 'nuclear', 'power_grid', 'cybersecurity')
    for factory in (x.auth, x.operation):
        with factory() as db:
            for tid in ids:
                if not db.get(Theme, tid):
                    db.add(Theme(theme_id=tid, display_name=tid, theme_type='theme', ticker='TEST',
                        market='US', currency='USD', active=True, universe_version='THEME_UNIVERSE_V0.1'))
            db.commit()
    for i in range(5):
        x.confirm(i)
    return x


def digest(factory, pids=None):
    # Hash fixture rows so assertion diagnostics never dump account/password data.
    result = {}
    with factory() as db:
        for table in Base.metadata.sorted_tables:
            query = select(table)
            if pids is not None:
                if 'participant_id' in table.c:
                    query = query.where(table.c.participant_id.in_(pids))
                elif table.name == 'demo_slots':
                    query = query.where(table.c.slot_number <= 5)
                else:
                    continue
            rows = sorted(json.dumps(dict(r), sort_keys=True, default=str) for r in db.execute(query).mappings())
            result[table.name] = sha256('\n'.join(rows).encode()).hexdigest()
    return result


def run(x, apply=False, **kwargs):
    return bootstrap.run_bootstrap(x.auth, x.operation, apply=apply, expected_cohort='shared-test', **kwargs)


def test_five_preserved_ten_distinct_initial_designs_and_idempotent_fifteen_ready(build):
    x = prepared(build)
    before = [digest(f) for f in (x.auth, x.operation)]
    preserved = [u['participant_id'] for u in x.users[:5]]
    protected = [digest(f, preserved) for f in (x.auth, x.operation)]
    preview = run(x)
    assert preview['ready_before'] == preview['ready_after'] == 5
    assert preview['projected_ready'] == 15 and len(preview['plans']) == 10
    assert {p['risk'] for p in preview['plans']} == {'stable','neutral','aggressive'}
    assert len({tuple(p['theme_ids']) for p in preview['plans']}) == 10
    assert all(p['new_decision']['decision_id'] is None and p['new_decision']['version'] == 1 for p in preview['plans'])
    assert before == [digest(f) for f in (x.auth, x.operation)]
    applied = run(x, True)
    assert applied['status'] == 'READY' and applied['ready_after'] == 15
    assert len(applied['created_decisions']) == 10
    assert protected == [digest(f, preserved) for f in (x.auth, x.operation)]
    for table in ('orders','trades','holdings_daily','nav_daily','prices_daily'):
        assert digest(x.operation)[table] == before[1][table]
    with x.operation() as db:
        new = list(db.scalars(select(PortfolioDecision).where(PortfolioDecision.participant_id.not_in(preserved))))
        assert len(new) == 10 and all(d.version == 1 and d.previous_decision_id is None for d in new)
        assert all(d.reason.startswith(bootstrap.KIND) for d in new)
        assert all(d.provenance_json.get('internal_tracking',{}).get('frontier') for d in new)
    complete = [digest(f) for f in (x.auth, x.operation)]
    assert run(x, True)['created_decisions'] == []
    assert complete == [digest(f) for f in (x.auth, x.operation)]


def test_dry_run_cli_requires_explicit_mode_and_never_writes(build, capsys):
    x = prepared(build)
    before = [digest(f) for f in (x.auth, x.operation)]
    with pytest.raises(SystemExit):
        bootstrap.main(['--expected-cohort','shared-test'])
    with pytest.raises(SystemExit):
        bootstrap.main(['--dry-run','--apply','--expected-cohort','shared-test'])
    capsys.readouterr()
    assert bootstrap.main(['--dry-run','--expected-cohort','shared-test']) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['mode'] == 'DRY_RUN' and len(data['plans']) == 10
    assert before == [digest(f) for f in (x.auth, x.operation)]


def test_existing_unready_decision_and_user_drafts_are_skipped(build):
    x = prepared(build)
    x.confirm(5)
    with x.auth() as db:
        db.get(DemoSlot, 'slot-5').confirmed_at = None
        db.get(DemoSlot, 'slot-6').draft_json = {'frontier_id':'F001','theme_ids':['ai']}
        db.commit()
    with x.operation() as db:
        u = x.users[7]
        db.add(OnboardingDraft(user_id=u['user_id'], participant_id=u['participant_id'],
            frontier_id='F002', theme_ids_json=['ai'], current_step='themes',
            created_at=C.now_utc(), updated_at=C.now_utc()))
        db.add(View(view_id='V-PRESERVED', participant_id=x.users[8]['participant_id'],
            theme_id='ai', status='new', submitted_at=C.now_utc(), effective_at=C.now_utc().date(),
            reason='existing choice', theme_universe_version='THEME_UNIVERSE_V0.1',
            cycle_week=C.now_utc().date(), cycle_date=C.now_utc().date()))
        db.commit()
    before = [digest(f) for f in (x.auth, x.operation)]
    preview = run(x)
    codes = {s['reason'] for s in preview['skipped']}
    assert {'EXISTING_DECISION_PRESERVED','EXISTING_DRAFT_PRESERVED',
            'EXISTING_THEME_CONFIGURATION_PRESERVED'} <= codes
    assert len(preview['plans']) == 6
    assert before == [digest(f) for f in (x.auth, x.operation)]


def test_first_use_workspace_uses_service_without_creating_operating_history(build):
    x = prepared(build)
    pid, uid = x.users[5]['participant_id'], x.users[5]['user_id']
    with x.operation() as db:
        aids = select(Account.account_id).where(Account.participant_id == pid)
        db.execute(delete(PortfolioTarget).where(PortfolioTarget.account_id.in_(aids)))
        db.execute(delete(Event).where(Event.participant_id == pid))
        db.execute(delete(User).where(User.user_id == uid))
        db.execute(delete(Account).where(Account.participant_id == pid))
        db.execute(delete(Participant).where(Participant.participant_id == pid))
        db.commit()
    result = run(x, True)
    assert result['ready_after'] == 15
    with x.operation() as db:
        assert db.get(User, uid).password_hash == '!identity-reference-only'
        assert len(list(db.scalars(select(Account).where(Account.participant_id == pid)))) == 2


def test_mid_failure_rolls_back_then_resume_keeps_deterministic_assignment(build, monkeypatch):
    x = prepared(build)
    original = {p['participant_id']:(p['risk'],p['theme_ids']) for p in run(x)['plans']}
    complete = onboarding_service.complete
    target = x.users[6]['user_id']
    def fault(session, uid, *args, **kwargs):
        if uid == target:
            complete(session, uid, *args, **kwargs)
            raise RuntimeError('PRIVATE_SENTINEL_DO_NOT_LOG')
        return complete(session, uid, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(onboarding_service, 'complete', fault)
        partial = run(x, True)
    assert partial['status'] == 'FAILED' and partial['ready_after'] == 6
    assert len(partial['created_decisions']) == 1
    assert 'PRIVATE_SENTINEL' not in json.dumps(partial)
    remaining = run(x)
    assert all(original[p['participant_id']] == (p['risk'],p['theme_ids']) for p in remaining['plans'])
    resumed = run(x, True)
    assert resumed['ready_after'] == 15, resumed['failures']
    with x.operation() as db:
        assert len(list(db.scalars(select(PortfolioDecision)))) == 15


def test_auth_commit_failure_preserves_decision_and_requires_reconciliation(build):
    x = prepared(build)
    def failing_auth():
        db = x.auth()
        def fault():
            raise RuntimeError('PRIVATE_SENTINEL_DO_NOT_LOG')
        db.commit = fault
        return db
    result = bootstrap.run_bootstrap(failing_auth, x.operation, apply=True, expected_cohort='shared-test')
    assert result['status'] == 'FAILED' and result['ready_after'] == 5
    assert result['failures'][0]['requires_reconciliation']
    with x.operation() as db:
        assert db.get(PortfolioDecision, result['failures'][0]['persisted_decision_id']) is not None
    before = digest(x.operation)
    preview = run(x)
    assert any(s['reason'] == 'EXISTING_DECISION_PRESERVED' for s in preview['skipped'])
    assert before == digest(x.operation)


def test_wrong_cohort_or_too_many_candidates_never_writes(build):
    x = prepared(build)
    before = [digest(f) for f in (x.auth, x.operation)]
    with pytest.raises(bootstrap.BootstrapError, match='COHORT_OR_CAPACITY_MISMATCH'):
        bootstrap.run_bootstrap(x.auth, x.operation, apply=True, expected_cohort='wrong')
    with pytest.raises(bootstrap.BootstrapError, match='MAX_NEW_EXCEEDED'):
        run(x, True, max_new=9)
    assert before == [digest(f) for f in (x.auth, x.operation)]


def test_prepared_legacy_five_plus_ten_reserved_slots_use_exact_daily_roster(build):
    from src.local.capstone import EMAILS
    x = prepared(build)
    with x.auth() as db:
        db.get(DemoCohort, 'shared-test').prepared_count = 5
        db.execute(delete(DemoSlot).where(DemoSlot.slot_number <= 5))
        for index, info in enumerate(x.users[:5]):
            user = db.get(User, info['user_id'])
            user.email = user.email_normalized = EMAILS[index]
        db.commit()
    protected = [digest(f, [u['participant_id'] for u in x.users[:5]]) for f in (x.auth,x.operation)]
    preview = run(x)
    assert preview['ready_before'] == 5 and len(preview['plans']) == 10
    assert run(x,True)['ready_after'] == 15
    assert protected == [digest(f, [u['participant_id'] for u in x.users[:5]]) for f in (x.auth,x.operation)]


def test_dry_preview_database_write_attempt_is_rejected_without_secret_output(build, monkeypatch, capsys):
    from src.db.models.operational import Counter
    x = prepared(build)
    before = [digest(f) for f in (x.auth,x.operation)]
    def writes(db, *args):
        db.add(Counter(name='PRIVATE_SENTINEL_DO_NOT_LOG',value=1))
        db.flush()
    monkeypatch.setattr(onboarding_service,'preview',writes)
    assert bootstrap.main(['--dry-run','--expected-cohort','shared-test']) == 1
    assert 'PRIVATE_SENTINEL' not in capsys.readouterr().out
    assert before == [digest(f) for f in (x.auth,x.operation)]


def test_invalid_frontier_cache_does_not_trigger_regeneration(build, monkeypatch, tmp_path):
    x = prepared(build)
    before = [digest(f) for f in (x.auth,x.operation)]
    cache = tmp_path/'no-regeneration'/'outputs/api/frontier.json'
    cache.parent.mkdir(parents=True)
    cache.write_text('{invalid json')
    monkeypatch.setattr(bootstrap,'ROOT',cache.parents[2])
    with pytest.raises(bootstrap.BootstrapError, match='VALID_FRONTIER_CACHE_REQUIRED'):
        run(x)
    assert cache.read_text() == '{invalid json'
    assert before == [digest(f) for f in (x.auth,x.operation)]

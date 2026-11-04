#!/usr/bin/env python3
"""Explicit professor-demo setup. Never schedules T0 or runs forward trading."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from itertools import combinations
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select, text, or_
from sqlalchemy.engine import make_url

from src.api.design_workspace import ensure_design_identity, _identity
from src.api.services import onboarding_service as onboarding, enrollment_service as enrollment
from src.api.services import decision_service, _common as C
from src.api.services.frontier_service import get_frontier, FRONTIER_VERSION
from src.api.services.strategy_service import require_executable
from src.db.config import capstone_mode, get_database_url, get_design_database_url
from src.db.models import (User, Participant, Account, PortfolioDecision, PortfolioTarget,
                          BasePortfolioSelection, Order, Trade, NavDaily, Theme, View)
from src.db.models.demo_cohort import DemoSlot
from src.db.models.onboarding import OnboardingDraft
from src.db.session import create_app_engine, session_factory
from src.forward import competition

KIND = 'PROFESSOR_DEMO_BOOTSTRAP_V1'


class BootstrapError(RuntimeError):
    """Safe operator code only: no credentials or raw database errors."""


@contextmanager
def readonly(factory):
    with factory() as db:
        conn = db.connection()
        sqlite = conn.dialect.name == 'sqlite'
        conn.execute(text('PRAGMA query_only=ON' if sqlite else 'SET TRANSACTION READ ONLY'))
        try:
            yield db
        finally:
            if sqlite:
                # Reset the SAME pooled connection before rollback releases it.
                conn.execute(text('PRAGMA query_only=OFF'))
            db.rollback()


def current_status(design_factory):
    """Exact daily READY logic, without connect()/schema initialization."""
    cohort = competition.read_cohort()
    if not cohort:
        raise BootstrapError('ACTIVE_COHORT_REQUIRED')
    url = design_factory.kw['bind'].url
    if url.get_backend_name() == 'sqlite':
        path = Path(url.database.removeprefix('file:')).resolve()
        con = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA query_only=ON')
    else:
        from src.forward.pg_adapter import connect_postgres
        # Preserve libpq URL encoding/options from the application's original URL.
        con = connect_postgres(get_design_database_url())
        con.execute('SET TRANSACTION READ ONLY')
    try:
        members, ready, all_ready = competition.readiness(con, cohort)
        scheduled = competition.saved_start(con)
        return {'cohort_id': cohort['cohort_id'], 'ready': ready, 'required': cohort['required'],
                'all_ready': all_ready, 'members': members, 'scheduled': bool(scheduled)}
    finally:
        con.close()


def initial_problem(auth, design, user, slot):
    if not user or user.role != 'user' or user.status != 'active' or not user.participant_id:
        return 'ACTIVE_LINKED_USER_REQUIRED'
    if not slot or slot.confirmed_at or slot.configuration_json or slot.forward_started_at:
        return 'EXISTING_OR_UNAVAILABLE_ENROLLMENT'
    pid, uid = user.participant_id, user.user_id
    for db in (auth, design):
        if db.scalar(select(PortfolioDecision.decision_id).where(or_(
                PortfolioDecision.user_id == uid, PortfolioDecision.participant_id == pid)).limit(1)):
            return 'EXISTING_DECISION_PRESERVED'
        if db.scalar(select(BasePortfolioSelection.selection_id).where(or_(
                BasePortfolioSelection.user_id == uid, BasePortfolioSelection.participant_id == pid)).limit(1)):
            return 'EXISTING_PORTFOLIO_PRESERVED'
        if db.scalar(select(View.view_id).where(View.participant_id == pid).limit(1)):
            return 'EXISTING_THEME_CONFIGURATION_PRESERVED'
        aids = select(Account.account_id).where(Account.participant_id == pid)
        if db.scalar(select(PortfolioTarget.target_id).where(
                PortfolioTarget.account_id.in_(aids), PortfolioTarget.kind != 'core').limit(1)):
            return 'EXISTING_TARGET_PRESERVED'
        for model in (Order, Trade, NavDaily):
            if db.scalar(select(model).where(model.account_id.in_(aids)).limit(1)):
                return 'EXISTING_OPERATION_PRESERVED'
        draft = db.get(OnboardingDraft, uid)
        if draft and (draft.frontier_id or draft.theme_ids_json or draft.reason or draft.completed_at):
            return 'EXISTING_DRAFT_PRESERVED'
    if any((slot.draft_json or {}).get(k) for k in ('frontier_id', 'theme_ids', 'reason')):
        return 'EXISTING_DRAFT_PRESERVED'
    if enrollment.latest_reset(auth, pid):
        return 'RESET_HISTORY_PRESERVED'
    identity, participant = design.get(User, uid), design.get(Participant, pid)
    accounts = list(design.scalars(select(Account).where(Account.participant_id == pid)))
    if identity and (identity.participant_id != pid or identity.email_normalized != user.email_normalized):
        return 'IDENTITY_MISMATCH'
    if identity or participant or accounts:
        if not identity or not participant or participant.status != 'active' or len(accounts) != 2 or {
                a.account_type for a in accounts if a.status == 'active'} != {'personal', 'core'}:
            return 'INCOMPLETE_WORKSPACE_REQUIRES_REVIEW'
    return None


def assignments(auth, design, slots):
    # Reuse UI label boundaries and actual Frontier points, not invented weights.
    cache = ROOT / 'outputs/api/frontier.json'
    if not cache.is_file():
        raise BootstrapError('FRONTIER_CACHE_REQUIRED_FOR_NO_WRITE_PREVIEW')
    try:
        cached = json.loads(cache.read_text())
        if cached['frontier_version'] != FRONTIER_VERSION or not cached['points']:
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise BootstrapError('VALID_FRONTIER_CACHE_REQUIRED') from None
    points = get_frontier()['points']
    bands = [('stable', '안정형', 0, .06), ('neutral', '중립형', .06, .08),
             ('aggressive', '공격형', .10, float('inf'))]
    picks = []
    for key, label, lo, hi in bands:
        candidates = sorted((p for p in points if lo <= p['volatility'] < hi),
                            key=lambda p: (p['volatility'], p['frontier_id']))
        if not candidates:
            raise BootstrapError('FRONTIER_RISK_BAND_UNAVAILABLE')
        picks.append((key, label, candidates[len(candidates)//2]))
    def themes(db):
        return {t.theme_id for t in db.scalars(select(Theme).where(Theme.active.is_(True), Theme.ticker.is_not(None))) if t.ticker}
    ids = []
    for tid in sorted(themes(auth) & themes(design)):
        try:
            require_executable([tid])
        except Exception:
            continue
        ids.append(tid)
    options = [[t] for t in ids] + [list(pair) for pair in combinations(ids, 2)]
    if len(options) < len(slots):
        raise BootstrapError('INSUFFICIENT_DISTINCT_TRADABLE_THEME_COMBINATIONS')
    # All cohort slots participate in mapping, including preserved READY slots.
    # Therefore partial runs never shift the remaining assignments.
    out = {}
    for index, slot in enumerate(sorted(slots, key=lambda s: (s.slot_number, s.slot_id))):
        key, label, point = picks[index % 3]
        out[slot.user_id] = {'risk': key, 'risk_label': label, 'frontier_id': point['frontier_id'],
            'base_volatility': point['volatility'], 'theme_ids': options[index],
            'reason': f'{KIND}: professor demonstration; slot={slot.slot_number}; base_risk={key}',
            'rebalance_frequency': (slot.draft_json or {}).get('rebalance_frequency') or 'monthly',
            'core_id': C.load_forward_cfg()['forward_test']['benchmark_version']}
    return out


def run_bootstrap(auth_factory, design_factory, *, apply=False, expected_cohort, max_new=10):
    if not capstone_mode():
        raise BootstrapError('CAPSTONE_LOCAL_PROFILE_REQUIRED')
    before = current_status(design_factory)
    if before['cohort_id'] != expected_cohort or before['required'] != 15:
        raise BootstrapError('COHORT_OR_CAPACITY_MISMATCH')
    roster = before['members']
    if len(roster) != 15 or len({m['user_id'] for m in roster}) != 15 or len({m['participant_id'] for m in roster}) != 15:
        raise BootstrapError('FIFTEEN_DISTINCT_REGISTERED_PARTICIPANTS_REQUIRED')
    plans, skipped, created, failures = [], [], [], []
    with readonly(auth_factory) as auth, readonly(design_factory) as design:
        from src.forward.replay import read_metadata
        if read_metadata(design):
            raise BootstrapError('REPLAY_DATABASE_NOT_ALLOWED')
        slots = list(auth.scalars(select(DemoSlot).where(DemoSlot.cohort_id == expected_cohort)))
        unready = [m for m in roster if m['status'] != 'READY']
        if before['scheduled'] and unready:
            raise BootstrapError('SCHEDULED_COMPETITION_REQUIRES_REVIEW')
        mapping = assignments(auth, design, slots) if unready else {}
        slot_map = {s.user_id:s for s in slots}
        for member in roster:
            uid = member['user_id']
            if member['status'] == 'READY':
                skipped.append({'participant_id':member['participant_id'], 'reason':'READY_PRESERVED'})
                continue
            user, slot = auth.get(User, uid), slot_map.get(uid)
            problem = initial_problem(auth, design, user, slot)
            if problem:
                skipped.append({'participant_id':member['participant_id'], 'reason':problem})
                continue
            data = mapping[uid]
            draft = design.get(OnboardingDraft, uid)
            if draft and draft.rebalance_frequency:
                data['rebalance_frequency'] = draft.rebalance_frequency
            preview = onboarding.preview(design, uid, member['participant_id'], data['frontier_id'], data['theme_ids'])
            plans.append({'user_id':uid, 'participant_id':member['participant_id'], **data,
                'new_decision': {'decision_id':None, 'version':1,
                    'confirmed_at':'ACTUAL_APPLY_TIME',
                    'effective_date':decision_service.effective_day(C.now_utc()).isoformat(),
                    'weights':preview['personalized']['weights'],
                    'expected_metrics': {k:preview['personalized'][k] for k in ('expected_return','volatility','tracking_error')}}})
    if len(plans) > max_new or not 1 <= max_new <= 10:
        raise BootstrapError('MAX_NEW_EXCEEDED')
    if apply:
        for plan in plans:
            # Slot first; serialize parallel operator runs and normal enrollment.
            with auth_factory() as auth, design_factory() as design:
                phase = 'PREPARE'
                try:
                    user = auth.get(User, plan['user_id'])
                    slot = auth.scalar(select(DemoSlot).where(DemoSlot.user_id == plan['user_id'],
                        DemoSlot.cohort_id == expected_cohort).with_for_update())
                    if auth.get_bind().dialect.name == 'sqlite':
                        # Obtain writer lock just as the enrollment service does.
                        from sqlalchemy import update
                        auth.execute(update(DemoSlot).where(DemoSlot.slot_id == slot.slot_id).values(slot_number=DemoSlot.slot_number))
                        auth.refresh(slot)
                    account = design.scalar(select(Account).where(Account.participant_id == plan['participant_id'], Account.account_type == 'personal'))
                    if account:
                        decision_service.lock_account(design, account.account_id)
                    problem = initial_problem(auth, design, user, slot)
                    if problem:
                        auth.rollback(); design.rollback()
                        skipped.append({'participant_id':plan['participant_id'], 'reason':problem})
                        continue
                    ensure_design_identity(design, auth, user)
                    preview = onboarding.preview(design, user.user_id, user.participant_id, plan['frontier_id'], plan['theme_ids'])
                    data = {k:plan[k] for k in ('core_id','frontier_id','theme_ids','reason','rebalance_frequency')}
                    result = onboarding.complete(design, user.user_id, user.participant_id,
                        data['frontier_id'], data['theme_ids'], data['reason'],
                        confirmed_preview=preview, rebalance_frequency=data['rebalance_frequency'])
                    enrollment.confirm_forward_design(auth, user, data, preview)
                    # No distributed transaction: persist decision before READY.
                    phase = 'DESIGN_COMMIT'
                    design.commit()
                    phase = 'AUTH_COMMIT'
                    auth.commit()
                    created.append({'participant_id':user.participant_id, 'decision_id':result['decision_id'],
                                    'risk':plan['risk'], 'theme_ids':plan['theme_ids']})
                except Exception as error:
                    design.rollback(); auth.rollback()
                    failures.append({'participant_id':plan['participant_id'], 'phase':phase,
                        'error_type':type(error).__name__,
                        'persisted_decision_id':result['decision_id'] if phase == 'AUTH_COMMIT' else None,
                        'requires_reconciliation':phase == 'AUTH_COMMIT'})
                    break  # Preserve successes, do not hide a partial failure.
    after = current_status(design_factory)
    return {'mode':'APPLY' if apply else 'DRY_RUN', 'configuration_kind':KIND,
        'cohort_id':expected_cohort, 'ready_before':before['ready'], 'ready_after':after['ready'],
        'required':after['required'], 'projected_ready':before['ready'] + len(plans),
        'plans':plans, 'created_decisions':created, 'skipped':skipped, 'failures':failures,
        'status':'FAILED' if failures else 'READY' if after['all_ready'] else 'PLANNED' if not apply else 'INCOMPLETE'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-cohort', required=True, help='Active cohort identifier; never a DB URL')
    parser.add_argument('--max-new', type=int, default=10)
    args = parser.parse_args(argv)
    engines = []
    try:
        if not capstone_mode():
            raise BootstrapError('CAPSTONE_LOCAL_PROFILE_REQUIRED')
        urls = [get_database_url(), get_design_database_url()]
        if not urls[1] or _identity(urls[0]) == _identity(urls[1]):
            raise BootstrapError('SEPARATE_AUTH_DESIGN_DATABASES_REQUIRED')
        for url in urls:
            parsed = make_url(url)
            if parsed.get_backend_name() == 'sqlite':
                path = Path(parsed.database or '').resolve()
                if not path.is_file():
                    raise BootstrapError('EXISTING_DATABASE_REQUIRED')
                if args.dry_run:
                    parsed = parsed.set(database='file:'+str(path)).update_query_dict({'mode':'ro','uri':'true'})
            engines.append(create_app_engine(parsed.render_as_string(hide_password=False)))
        result = run_bootstrap(*(session_factory(e) for e in engines), apply=args.apply,
                               expected_cohort=args.expected_cohort, max_new=args.max_new)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(result['status'] in ('FAILED','INCOMPLETE'))
    except Exception as error:
        code = str(error) if isinstance(error, BootstrapError) else type(error).__name__
        print(json.dumps({'status':'FAILED','code':code}))
        return 1
    finally:
        for engine in engines:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())

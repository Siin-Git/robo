"""Read-only comparison of saved simulations, isolated from the forward ledger.

Only the existing comparison serializer may publish peer data. Raw archives,
amounts, orders, weights and decision identifiers never leave this service.
"""
from sqlalchemy import select
from ...db.models import User
from ...forward.performance_report import calculate_report
from ..errors import ApiError
from .historical_preview_service import own
from .ledger_comparison_service import overview, members


def cohort_key(report):
    keys = ('run_id', 'source_sha256', 'start', 'end', 'selection_basis', 'execution_basis', 'cost_bps')
    return tuple(report.get(k) for k in keys) if report and all(report.get(k) is not None for k in keys) else None


def archive_report(archive, period, start=None, end=None):
    """Rebase measured NAV using the same calculator as normal performance."""
    if not archive:
        result = calculate_report([], [], [], [], period)
    else:
        def inside(d):
            return (start is None or d >= start.isoformat()) and (end is None or d < end.isoformat())
        ledger = archive['ledger']
        snapshots = [s for s in ledger['snapshots'] if inside(s['date'])]
        nav = [{'date': s['date'], 'nav': s['nav'], 'cash': s['cash_balance'],
                'status': s['nav_status']} for s in snapshots]
        benchmark = [{'date': p['date'], 'nav': p['core_nav']} for p in archive['series']
                     if inside(p['date']) and p.get('core_nav') is not None]
        holdings = [{**h, 'date': s['date']} for s in snapshots for h in s['holdings']]
        trades = [{'date': t['execution_at'][:10], 'asset_id': t['asset_id'],
                   'quantity': t['quantity'], 'gross_value': t['gross_value'], 'cost': t['transaction_cost']}
                  for t in ledger['trades']]
        result = calculate_report(nav, benchmark, holdings, trades, period)
    result['data_kind'] = 'HISTORICAL_REPLAY'
    result['decision_context'] = {'status': 'RECORDED', 'active_decision': bool(archive)}
    return result


def comparison(auth_db, forward_db, design_db, user, period, basis, source):
    if source not in ('auto', 'forward', 'archive'):
        raise ApiError('INVALID_SOURCE', 'source must be auto, forward or archive', 400)
    # Explicit forward keeps the original endpoint behavior and avoids archive reads.
    if source == 'forward':
        result = overview(auth_db, forward_db, period, basis)
        result['selected_source'] = 'forward'
        return result
    mine = own(design_db, user.participant_id, user.user_id).get('report')
    key = cohort_key(mine)
    available = bool(key and mine.get('ledger', {}).get('snapshots'))
    if source == 'auto':
        result = overview(auth_db, forward_db, period, basis)
        if result['return_ranked'] >= 2 or not available:
            result.update(selected_source='forward', archive_available=available)
            return result
    archives = {}
    if available:
        for person in members(auth_db):
            owner = auth_db.scalar(select(User).where(User.participant_id == person.participant_id,
                                                     User.status == 'active', User.role == 'user'))
            saved = own(design_db, person.participant_id, owner.user_id).get('report') if owner else None
            if cohort_key(saved) == key and saved.get('ledger', {}).get('snapshots'):
                archives[person.participant_id] = saved
    result = overview(auth_db, design_db, period, basis,
        report_loader=lambda pid, period, start=None, end=None: archive_report(archives.get(pid), period, start, end))
    result.update(selected_source='archive', archive_available=available,
                  archive_start=mine['start'] if available else None)
    return result

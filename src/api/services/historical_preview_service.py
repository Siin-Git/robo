"""Read-only archived counterfactuals, never part of the forward ledger."""
from copy import deepcopy
from sqlalchemy import select
from ...db.models.account import Account
from ...db.models.decision import PortfolioDecision
from ...db.models.event import Event

EVENT_TYPE = 'HISTORICAL_REPLAY_ARCHIVED'


def own(session, participant_id, user_id, include_performance=False):
    account = session.scalar(select(Account).where(
        Account.participant_id == participant_id, Account.account_type == 'personal'))
    if account is None:
        return {'available': False}
    latest = session.scalar(select(PortfolioDecision).where(
        PortfolioDecision.account_id == account.account_id,
        PortfolioDecision.user_id == user_id).order_by(PortfolioDecision.version.desc()))
    if latest is None:
        return {'available': False}
    events = session.scalars(select(Event).where(
        Event.event_type == EVENT_TYPE, Event.account_id == account.account_id,
        Event.participant_id == participant_id).order_by(Event.timestamp.desc(), Event.event_id.desc()))
    for event in events:
        report = event.payload_json or {}
        if report.get('kind') != 'HISTORICAL_REPLAY' or not report.get('series'):
            continue
        decision = session.get(PortfolioDecision, report.get('decision_id'))
        if decision is None or decision.user_id != user_id or decision.account_id != account.account_id:
            continue
        result = deepcopy(report)
        result['is_current_configuration'] = decision.decision_id == latest.decision_id
        if include_performance and result.get('ledger', {}).get('snapshots'):
            # Derive attribution from the owner's immutable saved ledger using
            # the same NAV/P&L calculator as forward performance and ranking.
            from .archived_comparison_service import archive_report
            result['performance_report'] = archive_report(result, 'ALL')
        return {'available': True, 'report': result}
    return {'available': False}

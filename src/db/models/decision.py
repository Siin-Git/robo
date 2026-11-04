"""Append-only confirmed personal decisions and explicit user choices."""
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint, event, DDL
from sqlalchemy.orm import Mapped, mapped_column
from ..base import Base, DateCol, JSONBType, TZDateTime

class PortfolioDecision(Base):
    __tablename__ = "portfolio_decisions"
    __table_args__ = (UniqueConstraint("account_id", "version"),)
    decision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.participant_id"), nullable=False)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_decision_id: Mapped[str | None] = mapped_column(ForeignKey("portfolio_decisions.decision_id"))
    selection_id: Mapped[str] = mapped_column(ForeignKey("base_portfolio_selections.selection_id"), nullable=False)
    target_id: Mapped[str] = mapped_column(ForeignKey("portfolio_targets.target_id"), nullable=False)
    confirmed_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)
    effective_date: Mapped[object] = mapped_column(DateCol, nullable=False)
    weights_json: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    expectations_json: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    provenance_json: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)

class PortfolioChoice(Base):
    __tablename__ = "portfolio_choices"
    __table_args__ = (UniqueConstraint("user_id", "request_key"),
                      CheckConstraint("action IN ('KEEP','ADJUST')", name="choice_action"))
    choice_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    decision_id: Mapped[str] = mapped_column(ForeignKey("portfolio_decisions.decision_id"), nullable=False)
    target_id: Mapped[str] = mapped_column(ForeignKey("portfolio_targets.target_id"), nullable=False)
    action: Mapped[str] = mapped_column(String(8), nullable=False)
    selected_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    request_key: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    effect_json: Mapped[dict] = mapped_column(JSONBType, nullable=False)

# Enforce append-only storage even for direct SQL, on migrations and create_all.
for model in (PortfolioDecision, PortfolioChoice):
    table = model.__tablename__
    for operation in ("UPDATE", "DELETE"):
        event.listen(model.__table__, "after_create", DDL(
            f"CREATE TRIGGER {table}_{operation.lower()}_immutable BEFORE {operation} ON {table} "
            "BEGIN SELECT RAISE(ABORT, 'immutable portfolio record'); END"
        ).execute_if(dialect="sqlite"))
    event.listen(model.__table__, "after_create", DDL(
        f"CREATE OR REPLACE FUNCTION {table}_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN RAISE EXCEPTION 'immutable portfolio record'; END; $$"
    ).execute_if(dialect="postgresql"))
    event.listen(model.__table__, "after_create", DDL(
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {table}_immutable()"
    ).execute_if(dialect="postgresql"))

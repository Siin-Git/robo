"""Seed a scratch backend DB for E2E (themes only; users register via UI flow)."""
import os
import sys
from datetime import date

db = os.environ.get("E2E_SQLITE_PATH")
if not db:
    raise SystemExit("E2E_SQLITE_PATH is required")
if os.path.exists(db):
    os.remove(db)

sys.path.insert(0, ".")
from src.db.base import Base
from src.db.models.theme import Theme
from src.db.session import create_app_engine, session_factory

engine = create_app_engine(f"sqlite:///{db}")
Base.metadata.create_all(engine)
from sqlalchemy.orm import sessionmaker
S = sessionmaker(bind=engine, future=True)
with S() as s:
    for tid, name, ttype, ticker in [
        ("ai", "AI", "theme", "AIQ"),
        ("semiconductor", "Semi", "sector", "SOXX"),
        ("nuclear", "Nuclear", "theme", "URA"),
    ]:
        s.add(Theme(theme_id=tid, display_name=name, theme_type=ttype, ticker=ticker,
                    market="US", currency="USD", active=True,
                    valid_from=date(2026, 1, 1), valid_to=None,
                    universe_version="THEME_UNIVERSE_V0.1", inactive_reason=None))
    s.commit()
print("e2e backend seeded:", db)

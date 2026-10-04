"""Opt-in local replay reads; portfolio writes/reviews retain the design DB."""
import os
from pathlib import Path
from functools import lru_cache
from fastapi import Depends
from sqlalchemy import text
from ..db.session import create_app_engine, session_factory
from .design_workspace import get_design_db
from .dependencies import get_db


@lru_cache(maxsize=4)
def read_factory(path):
    engine = create_app_engine(f"sqlite:///{path}")
    return session_factory(engine)


def get_performance_db(design=Depends(get_design_db), auth=Depends(get_db)):
    directory = os.environ.get("COMPETITION_REPLAY_DIR")
    if not directory:
        yield design
        return
    from ..forward.replay import local_directory
    directory = local_directory(directory)
    if auth.get_bind().dialect.name != "sqlite" or Path(auth.get_bind().url.database).resolve().parent != directory:
        raise RuntimeError("Replay reads require the isolated local roster")
    path = directory / "replay_ledger.db"
    if not path.is_file():
        yield design  # Participants may complete setup while the run is prepared.
        return
    with read_factory(str(path))() as db:
        db.execute(text("PRAGMA query_only=ON"))
        yield db

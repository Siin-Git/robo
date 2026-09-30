"""마이그레이션이 모델을 빠짐없이 덮는지 확인한다.

SQLite 로 개발할 때는 ``Base.metadata.create_all`` 이 테이블을 만들어 주므로,
마이그레이션에 빠진 테이블이 있어도 아무 일이 없다. 그런데 PostgreSQL 배포는
``alembic upgrade head`` **만으로** 스키마를 만든다(``render.yaml`` 의
startCommand). 그래서 누락은 배포한 뒤 런타임에야 드러난다.

실제로 ``demo_cohorts`` 와 ``demo_slots`` 가 그렇게 빠져 있었다. 두 테이블은
초대 슬롯과 비교군 정원이 쓴다.

여기서는 마이그레이션을 **진짜로 돌려서** 만들어진 스키마와 모델을 비교한다.
이름만 본다(타입은 SQLite/PostgreSQL 이 다르다). 목적은 "테이블이나 컬럼이
통째로 빠졌는가" 를 잡는 것이다.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

pytest.importorskip("alembic", reason="alembic 이 없으면 마이그레이션을 돌릴 수 없다")


@pytest.fixture(scope="module")
def migrated(tmp_path_factory):
    """빈 SQLite 에 alembic upgrade head 를 돌린 결과."""
    db = tmp_path_factory.mktemp("alembic") / "head.db"
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{db}",
               DATABASE_BACKEND="sqlite", PYTHONPATH=str(ROOT))
    env.pop("CAPSTONE_DEMO", None)          # 개발자 환경이 새지 않게
    env.pop("CAPSTONE_DESIGN_DATABASE_URL", None)
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                            cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"alembic upgrade head 실패\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    return db


def _actual(db):
    from sqlalchemy import create_engine, inspect
    insp = inspect(create_engine(f"sqlite:///{db}"))
    return {t: {c["name"] for c in insp.get_columns(t)}
            for t in insp.get_table_names() if t != "alembic_version"}


def _expected():
    from src.db.base import Base
    import src.db.models  # noqa: F401  (모든 모델 등록)
    return {name: set(table.columns.keys())
            for name, table in Base.metadata.tables.items()}


def test_모든_모델_테이블이_마이그레이션에_있다(migrated):
    missing = sorted(set(_expected()) - set(_actual(migrated)))
    assert not missing, (
        f"모델에는 있는데 마이그레이션이 만들지 않는 테이블: {missing}. "
        f"PostgreSQL 배포에서 런타임에 죽는다.")


def test_마이그레이션이_모델에_없는_테이블을_만들지_않는다(migrated):
    extra = sorted(set(_actual(migrated)) - set(_expected()))
    assert not extra, f"모델에 없는 테이블을 만든다: {extra}"


def test_컬럼이_빠지지_않았다(migrated):
    actual, expected = _actual(migrated), _expected()
    problems = []
    for table, columns in expected.items():
        if table not in actual:
            continue                       # 위 테스트가 따로 보고한다
        gap = sorted(columns - actual[table])
        if gap:
            problems.append(f"{table}: {gap}")
    assert not problems, "마이그레이션에 빠진 컬럼:\n  " + "\n  ".join(problems)


def test_리비전이_한_줄로_이어진다():
    """분기가 생기면 alembic upgrade head 가 어느 쪽인지 모른다."""
    import ast
    revisions, downs = {}, {}
    for f in sorted((ROOT / "migrations" / "versions").glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            name = getattr(node.targets[0], "id", "")
            if name == "revision":
                revisions[node.value.value] = f.name
            elif name == "down_revision":
                downs[f.name] = node.value.value
    assert len(revisions) == len(downs), "revision 을 선언하지 않은 파일이 있다"
    parents = [d for d in downs.values() if d is not None]
    assert len(parents) == len(set(parents)), (
        f"같은 부모를 가리키는 마이그레이션이 둘 이상이다(분기): {parents}")
    roots = [f for f, d in downs.items() if d is None]
    assert len(roots) == 1, f"시작점이 여럿이다: {roots}"


# --------------------------------------------------------------------------
# 이전 도구도 모델을 빠짐없이 덮어야 한다
# --------------------------------------------------------------------------

def _script_const(name: str, const: str):
    """스크립트를 import 하지 않고 상수만 읽는다(DB 접속을 피하려고)."""
    import ast
    src = (ROOT / "scripts" / name).read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == const:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} 에 {const} 가 없다")


def test_이전_도구가_모든_모델_테이블을_옮긴다():
    """원장만 옮기고 로그인 계정을 두고 오면, 옮긴 뒤 아무도 못 들어온다.

    실제로 users, sessions, base_portfolio_selections, onboarding_drafts,
    demo_cohorts, demo_slots, scheduled_jobs 일곱이 빠져 있었다.
    """
    from src.db.base import Base
    import src.db.models  # noqa: F401
    covered = set(_script_const("migrate_sqlite_to_postgres.py", "TABLE_ORDER"))
    missing = sorted(set(Base.metadata.tables) - covered)
    assert not missing, f"이전 도구가 다루지 않는 테이블: {missing}"


def test_검증_도구도_같은_목록을_본다():
    """옮기는 목록과 검증하는 목록이 다르면, 검증을 통과해도 빠진 게 있다."""
    a = _script_const("migrate_sqlite_to_postgres.py", "TABLE_ORDER")
    b = _script_const("verify_db_parity.py", "TABLE_ORDER")
    assert a == b


def test_부모_테이블이_자식보다_먼저_온다():
    """외래키 때문에 순서가 틀리면 삽입이 실패한다."""
    order = _script_const("migrate_sqlite_to_postgres.py", "TABLE_ORDER")
    fks = _script_const("migrate_sqlite_to_postgres.py", "FK_PARENTS")
    position = {t: i for i, t in enumerate(order)}
    for child, rules in fks.items():
        for _col, parent, _pcol in rules:
            assert parent in position, f"{parent} 가 TABLE_ORDER 에 없다"
            assert position[parent] <= position[child], (
                f"{parent} 가 {child} 보다 뒤에 온다")


def test_원장_테이블은_건너뛸_수_없다():
    """인증 테이블은 없을 수 있어도 원장이 없으면 옮기면 안 된다."""
    required = set(_script_const("migrate_sqlite_to_postgres.py", "REQUIRED_TABLES"))
    for t in ("orders", "trades", "holdings_daily", "nav_daily", "prices_daily"):
        assert t in required, f"{t} 가 필수 목록에 없다"
    assert "sessions" not in required

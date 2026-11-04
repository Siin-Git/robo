"""시연 인원을 늘릴 때 같이 고쳐야 하는 것들을 고정한다.

인원수가 예전에는 ``range(1, 14)`` 로 capstone.py 에 박혀 있었고, 화면 정원과
랩미팅 검증에는 숫자 13 이 따로 박혀 있었다. COHORT 만 늘리면 이메일이
따라오지 않아 조용히 어긋난다. 여기서 그 연결을 못으로 박아 둔다.

소스를 ast 로 읽는 항목이 하나 있다(``seed_capstone.paths`` 의 테마 계수).
그 함수를 import 하려면 DB 계층 전체가 따라와서, 값만 꺼내 확인한다.
"""
import ast
from pathlib import Path

import yaml

from src.local.capstone import COHORT, COHORT_SIZE, EMAILS

ROOT = Path(__file__).resolve().parents[2]


def test_이메일이_인원수를_따라온다():
    """COHORT 만 늘리고 EMAILS 를 잊으면 마지막 사람이 로그인하지 못한다."""
    assert len(EMAILS) == len(COHORT) == COHORT_SIZE


def test_이메일이_1번부터_빠짐없이_붙는다():
    assert EMAILS == [f"capstone{i:02d}@example.com"
                      for i in range(1, len(COHORT) + 1)]
    assert len(set(EMAILS)) == len(EMAILS)


def test_테마_쌍이_겹치지_않는다():
    """시나리오는 테마 조합으로 찾는다(enrollment_service 의 scenario 매칭).

    두 참가자가 같은 조합을 가지면 first-match 가 먼저 사람을 집어서
    엉뚱한 시연 자료가 붙는다.
    """
    pairs = [tuple(sorted(themes)) for _, themes in COHORT]
    duplicated = sorted({p for p in pairs if pairs.count(p) > 1})
    assert not duplicated, f"중복된 테마 조합: {duplicated}"


def test_모든_테마가_유니버스에_있다():
    with (ROOT / "config/themes_v01.yaml").open(encoding="utf-8") as f:
        known = {t["theme_id"] for t in yaml.safe_load(f)["themes"]}
    used = {t for _, themes in COHORT for t in themes}
    assert used <= known, f"유니버스에 없는 테마: {sorted(used - known)}"


def test_모든_테마에_시연용_NAV_계수가_있다():
    """``paths()`` 의 params 에 없는 테마를 쓰면 시드가 KeyError 로 죽는다."""
    source = (ROOT / "src/local/seed_capstone.py").read_text(encoding="utf-8")
    paths = next(n for n in ast.parse(source).body
                 if isinstance(n, ast.FunctionDef) and n.name == "paths")
    params = next(n.value for n in ast.walk(paths)
                  if isinstance(n, ast.Assign)
                  and getattr(n.targets[0], "id", None) == "params")
    known = {k.value for k in params.keys}
    used = {t for _, themes in COHORT for t in themes}
    assert used <= known, f"NAV 계수가 없는 테마: {sorted(used - known)}"


def test_참가자_이름이_번호와_맞는다():
    """View 의 id 가 CD{번호}V{k} 라 이름과 번호가 어긋나면 헷갈린다."""
    for i, (name, _) in enumerate(COHORT, 1):
        assert name.endswith(f"{i:02d}"), f"{i}번째 참가자 이름: {name!r}"

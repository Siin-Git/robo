from datetime import datetime, timezone, timedelta
from scripts.verify_db_parity import values_equal

def test_same_instant_survives_postgres_session_timezone():
    utc=datetime(2026,10,3,2,37,36,107635,tzinfo=timezone.utc)
    kst=utc.astimezone(timezone(timedelta(hours=9)))
    assert values_equal(utc,kst)
    assert values_equal(utc,utc.replace(tzinfo=None))
    assert not values_equal(utc,kst+timedelta(seconds=1))

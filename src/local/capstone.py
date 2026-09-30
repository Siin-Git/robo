"""Fixed demo cohort. No strategy or live trading behavior lives here."""
import os

COHORT = [
    ("참여자 01", ["semiconductor", "ai"]),
    ("참여자 02", ["defense", "nuclear"]),
    ("참여자 03", ["power_grid", "cybersecurity"]),
    ("참여자 04", ["ai", "robotics"]),
    ("참여자 05", ["biotech", "nuclear"]),
    ("참여자 06", ["semiconductor", "defense"]),
    ("참여자 07", ["cloud_data_center", "ai"]),
    ("참여자 08", ["robotics", "biotech"]),
    ("참여자 09", ["defense", "power_grid"]),
    ("참여자 10", ["nuclear", "semiconductor"]),
    ("참여자 11", ["cybersecurity", "cloud_data_center"]),
    ("참여자 12", ["biotech", "cloud_data_center"]),
    ("참여자 13", ["robotics", "power_grid"]),
    ("참여자 14", ["cybersecurity", "robotics"]),
    ("참여자 15", ["ai", "power_grid"]),
]
# 인원수는 COHORT 하나에서만 정한다. 예전에는 range(1, 14) 로 박혀 있어
# COHORT 를 늘려도 이메일이 따라오지 않았다.
EMAILS = [f"capstone{i:02d}@example.com" for i in range(1, len(COHORT) + 1)]
COHORT_SIZE = len(COHORT)
PASSWORD = "Capstone-Demo-2026!"  # Public local-demo credential, never a production secret.


def enabled():
    return (os.environ.get("CAPSTONE_DEMO") == "1"
            and os.environ.get("APP_PROFILE") == "local")

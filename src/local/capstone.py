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
]
EMAILS = [f"capstone{i:02d}@example.com" for i in range(1, 14)]
PASSWORD = "Capstone-Demo-2026!"  # Public local-demo credential, never a production secret.


def enabled():
    return (os.environ.get("CAPSTONE_DEMO") == "1"
            and os.environ.get("APP_PROFILE") == "local")

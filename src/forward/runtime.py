"""Runtime profile resolver: single source of truth for environment separation.

Profiles: live / demo / validation. Every forward CLI resolves its database
through here and prints the safety banner. No module may hardcode a DB path.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PROFILES = ("live", "demo", "validation", "local")
DB_PATHS = {
    "live": "data/forward_test.db",
    "demo": "data/forward_demo.db",
    "validation": "data/forward_validation.db",
    "local": "data/forward_local.db",
}


def get_runtime_profile() -> str:
    profile = os.environ.get("APP_PROFILE", "live").strip().lower()
    if profile not in PROFILES:
        raise ValueError(f"unknown APP_PROFILE={profile!r} (expected one of {PROFILES})")
    return profile


def get_database_path(profile: str | None = None) -> Path:
    profile = profile or get_runtime_profile()
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}")
    return ROOT / DB_PATHS[profile]


def safety_banner(profile: str | None = None) -> str:
    profile = profile or get_runtime_profile()
    db = get_database_path(profile)
    try:
        disp = str(db.relative_to(ROOT))
    except ValueError:
        disp = str(db)
    return ("=====================================\n"
            f"PROFILE: {profile.upper()}\n"
            f"DATABASE: {disp}\n"
            "=====================================")


def print_banner(profile: str | None = None) -> str:
    profile = profile or get_runtime_profile()
    print(safety_banner(profile), flush=True)
    return profile

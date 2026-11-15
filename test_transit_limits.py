"""
/api/transits input limits: one request can't run unbounded work.

Run from the repo root:  .venv/bin/python test_transit_limits.py

Each limit is checked at its edge: the largest allowed value builds a valid
TransitRequest, and one past it gets a 422 with a message naming the limit,
sent through FastAPI's TestClient. The callers' real shape (11 bodies plus
their _opp anti-points = 22 natal points, 548-day window, 4 aspects, 5
planets) must stay valid. Fixture birth data is synthetic (no real person).
"""
import os
import sys

os.environ.setdefault("AUTH_MODE", "cloud-run-iam")
os.environ.pop("API_KEY", None)

from fastapi.testclient import TestClient
from pydantic import ValidationError

import server

client = TestClient(server.app)

BODIES = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto"]
ASPECTS_SIX = {
    "Conjunction": {"angle": 0, "orb": 1.0}, "Sextile": {"angle": 60, "orb": 1.0},
    "Square": {"angle": 90, "orb": 1.0}, "Trine": {"angle": 120, "orb": 1.0},
    "Quincunx": {"angle": 150, "orb": 1.0}, "Opposition": {"angle": 180, "orb": 1.0},
}


def natal(n):
    return {f"p{i}": float(i * 10 % 360) for i in range(n)}


def payload(**overrides):
    body = dict(
        natal_positions=natal(2), start_date="2026-01-01", end_date="2026-02-01",
        lat=40.7128, lon=-74.0060, birth_year=1990, birth_month=1, birth_day=1,
        birth_hour=12, birth_min=0, house_type="P",
        transiting_planets=["jupiter", "saturn"],
        aspects={"Conjunction": {"angle": 0, "orb": 1.0}},
    )
    body.update(overrides)
    return body


def is_valid(**overrides):
    try:
        server.TransitRequest(**payload(**overrides))
        return True
    except ValidationError:
        return False


def rejected(expected_text, **overrides):
    r = client.post("/api/transits", json=payload(**overrides))
    return r.status_code == 422 and expected_text in r.text, f"{r.status_code} {r.text[:200]}"


passes = failures = 0


def check(name, cond, detail=""):
    global passes, failures
    passes, failures = passes + bool(cond), failures + (not cond)
    print(f"  {'✓' if cond else '✗'} {name}{f'  ({detail})' if detail and not cond else ''}")


def check_rejected(name, expected_text, **overrides):
    ok, detail = rejected(expected_text, **overrides)
    check(name, ok, detail)


print("\n1. callers' real request shape stays valid")
real_natal = {}
for body in ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto", "asc"]:
    real_natal[body] = 100.0
    real_natal[f"{body}_opp"] = 280.0
check("22 natal points, 548 days, 4 aspects, 5 planets", is_valid(
    natal_positions=real_natal, start_date="2026-01-01", end_date="2027-07-03",
    transiting_planets=["jupiter", "saturn", "uranus", "neptune", "pluto"],
    aspects={k: ASPECTS_SIX[k] for k in ["Conjunction", "Square", "Opposition", "Quincunx"]}))

print("\n2. date order and span")
check("two years across a leap day (731 days) allowed", is_valid(start_date="2027-03-01", end_date="2029-03-01"))
check_rejected("732-day span → 422", "at most 731 days", start_date="2027-03-01", end_date="2029-03-02")
check_rejected("end_date equal to start_date → 422", "end_date must be after start_date",
               start_date="2026-01-01", end_date="2026-01-01")
check_rejected("end_date before start_date → 422", "end_date must be after start_date",
               start_date="2026-02-01", end_date="2026-01-01")

print("\n3. natal_positions")
check("24 natal positions allowed", is_valid(natal_positions=natal(24)))
check_rejected("25 natal positions → 422", "At most 24 natal positions", natal_positions=natal(25))

print("\n4. aspects")
check("6 aspects allowed", is_valid(aspects=ASPECTS_SIX))
check_rejected("7 aspects → 422", "At most 6 aspects",
               aspects={**ASPECTS_SIX, "Semisquare": {"angle": 45, "orb": 1.0}})

print("\n5. transiting_planets")
check("all 10 bodies allowed", is_valid(transiting_planets=BODIES))
check_rejected("11 entries → 422", "At most 10 transiting planets", transiting_planets=BODIES + ["chiron"])
check_rejected("duplicate body → 422", "duplicates: ['saturn']", transiting_planets=["saturn", "jupiter", "saturn"])

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)

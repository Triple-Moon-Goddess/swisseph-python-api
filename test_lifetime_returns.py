"""Offline verification of /api/lifetime-returns.

Run from the repo root:  .venv/bin/python test_lifetime_returns.py

Calls the endpoint function directly (no HTTP, no API key) and asserts
against independently known ephemeris facts: a solar return falls on every
birthday, Saturn returns at ~29.5-year spacing, the Uranus opposition lands
mid-life and the Uranus return in the early eighties, and the post-natal
wobble is never a return (the /api/returns departure gate). Fixture birth
data is synthetic (no real person): 1990-01-01 12:00, New York — the same
chart test_annual_transits.py uses.
"""
import swisseph as swe

import server

FIXTURE_BIRTH = dict(
    birth_year=1990, birth_month=1, birth_day=1, birth_hour=12, birth_min=0,
    lat=40.7128, lon=-74.0060, house_type="placidus",
)


def fixture_natal_positions():
    bjd = server.calculate_julian_day(1990, 1, 1, 12, 0, 40.7128, -74.0060)
    return {body: server.get_transit_lon(bjd, pid) for body, pid in server.INGRESS_PLANET_IDS.items()}


def years_between(iso_a: str, iso_b: str) -> float:
    ya, yb = int(iso_a[:4]), int(iso_b[:4])
    return yb - ya + (int(iso_b[5:7]) - int(iso_a[5:7])) / 12.0


def main():
    failures = []

    def check(name, cond, detail=""):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {name} {detail}")
        if not cond:
            failures.append(name)

    natal = fixture_natal_positions()

    print("== /api/lifetime-returns: synthetic 1990 chart, 126 years ==")
    req = server.LifetimeReturnsRequest(natal_positions=natal, **FIXTURE_BIRTH)
    out = server.get_lifetime_returns(req, api_key="local")

    check("birth instant echoed (UT of 12:00 New York)", out["birth_instant"].startswith("1990-01-01T17:00"), out["birth_instant"])
    check("scan ends at the 126th birthday", out["end_instant"].startswith("2116-01-0"), out["end_instant"])
    check("default bodies exclude the Moon", set(out["returns"]) == set(server.LIFETIME_RETURN_BODIES) and "moon" not in out["returns"])
    check("default oppositions are Uranus only", list(out["oppositions"]) == ["uranus"])

    sun = out["returns"]["sun"]
    check("one solar return per year of life (126)", len(sun) == 126, len(sun))
    check("every solar return is on or beside the birthday",
          all(r["date"][5:10] in ("12-31", "01-01", "01-02") for r in sun), sorted({r["date"][5:10] for r in sun}))
    check("first solar return is age 1, not the birth instant", sun[0]["date"].startswith("1991-01-01"), sun[0]["date"])
    check("solar return sits at the natal Sun degree", abs(server.wrap180(sun[0]["longitude"] - natal["sun"])) < 1e-3, sun[0]["longitude"])
    check("crossings carry sign, degree and direction", all({"sign", "degree", "is_retro"} <= set(r) for r in sun))

    saturn = out["returns"]["saturn"]
    check("no Saturn return before age 27 (post-natal wobble gated out)", saturn[0]["date"] >= "2017", saturn[0]["date"])
    check("first Saturn return in the 29th year (2019 for a 1990 birth)", saturn[0]["date"].startswith("2019"), saturn[0]["date"])
    first_pass_years = years_between(saturn[0]["date"], [r for r in saturn if r["date"] >= "2045"][0]["date"])
    check("second Saturn return ~29.5 years after the first", 28.0 <= first_pass_years <= 31.0, first_pass_years)

    jupiter = out["returns"]["jupiter"]
    check("first Jupiter return near age 12", jupiter[0]["date"][:4] in ("2001", "2002"), jupiter[0]["date"])
    check("~10 Jupiter cycles in 126 years (multi-pass counted)", 10 <= len(jupiter) <= 32, len(jupiter))

    uranus = out["returns"]["uranus"]
    check("Uranus return in the 84th year (2073–2074)", uranus[0]["date"][:4] in ("2073", "2074"), uranus[0]["date"])
    opposed = out["oppositions"]["uranus"]
    check("Uranus opposition mid-life (2031–2035)", all(r["date"][:4] in ("2031", "2032", "2033", "2034", "2035") for r in opposed), [r["date"][:10] for r in opposed])
    check("Uranus opposition sits 180° from natal Uranus",
          all(abs(abs(server.wrap180(r["longitude"] - natal["uranus"])) - 180.0) < 1e-3 for r in opposed))
    check("no false opposition at the birth instant", opposed[0]["date"] > "1991")

    mercury = out["returns"]["mercury"]
    check("Mercury returns include retrograde passes", any(r["is_retro"] for r in mercury))
    check("Mercury crossings are chronological", all(a["date"] < b["date"] for a, b in zip(mercury, mercury[1:])))

    mars = out["returns"]["mars"]
    check("first Mars return in the second year of life", mars[0]["date"][:4] in ("1991", "1992"), mars[0]["date"])

    print("== validation ==")
    try:
        server.LifetimeReturnsRequest(natal_positions=natal, bodies=["moon"], **FIXTURE_BIRTH)
        check("the Moon is rejected as a lifetime body", False)
    except ValueError as e:
        check("the Moon is rejected as a lifetime body", "Lifetime bodies" in str(e))
    try:
        server.LifetimeReturnsRequest(natal_positions=natal, span_years=500, **FIXTURE_BIRTH)
        check("span_years is capped", False)
    except ValueError as e:
        check("span_years is capped", "span_years" in str(e))
    try:
        server.LifetimeReturnsRequest(natal_positions=natal, **dict(FIXTURE_BIRTH, lat=95))
        check("latitude range is enforced through the shared natal base", False)
    except ValueError as e:
        check("latitude range is enforced through the shared natal base", "Latitude" in str(e))
    try:
        server.get_lifetime_returns(server.LifetimeReturnsRequest(natal_positions={"sun": natal["sun"]}, **FIXTURE_BIRTH), api_key="local")
        check("missing natal positions are a 422", False)
    except server.HTTPException as e:
        check("missing natal positions are a 422", e.status_code == 422, e.detail)

    print("== /api/returns still validates through the shared base ==")
    ret = server.get_returns(server.ReturnsRequest(
        anchor_instant="2026-09-17T19:00:00", bodies=["saturn"], natal_positions=natal,
        current_lat=34.05, current_lon=-118.24, **FIXTURE_BIRTH), api_key="local")
    check("Saturn cycle around 2026 starts at the 2019 return", ret["returns"]["saturn"]["cycle"]["start"].startswith("2019"), ret["returns"]["saturn"]["cycle"]["start"])
    try:
        server.ReturnsRequest(anchor_instant="2026-09-17T19:00:00", natal_positions=natal, current_lat=95, current_lon=0, **FIXTURE_BIRTH)
        check("current_lat range still enforced", False)
    except ValueError as e:
        check("current_lat range still enforced", "Latitude" in str(e))

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {failures}")
        raise SystemExit(1)
    print("All lifetime-returns checks passed.")


if __name__ == "__main__":
    main()

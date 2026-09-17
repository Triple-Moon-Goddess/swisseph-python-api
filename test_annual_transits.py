"""Offline verification of /api/annual-transits.

Run from the repo root:  .venv/bin/python test_annual_transits.py

Calls the endpoint function directly (no HTTP, no API key) and asserts against
independently known ephemeris facts — the station, eclipse and outer-planet
ingress dates on the TMG Annual Transit Report template (2026-09-13 start),
which were checked against published ephemerides. Fixture birth data is
synthetic (no real person): 1990-01-01 12:00, New York.
"""
import swisseph as swe

import server

FIXTURE_BIRTH = dict(
    birth_year=1990, birth_month=1, birth_day=1, birth_hour=12, birth_min=0,
    lat=40.7128, lon=-74.0060, house_type="placidus",
)


def fixture_targets():
    bjd = server.calculate_julian_day(1990, 1, 1, 12, 0, 40.7128, -74.0060)
    houses, _ = server.calculate_houses_for_jd(bjd, 40.7128, -74.0060, "placidus")
    asc = houses["ascendant"]["longitude"]
    mc = houses["midheaven"]["longitude"]
    return {
        "sun": server.get_transit_lon(bjd, swe.SUN),
        "ascendant": asc,
        "ic": (mc + 180.0) % 360.0,
        "descendant": (asc + 180.0) % 360.0,
        "midheaven": mc,
    }


def main():
    failures = []

    def check(name, cond, detail=""):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {name} {detail}")
        if not cond:
            failures.append(name)

    print("== /api/annual-transits: 2026-09-13 start, synthetic 1990 chart ==")
    req = server.AnnualTransitsRequest(
        start_instant="2026-09-13T07:00:00", sun_targets=fixture_targets(), **FIXTURE_BIRTH)
    out = server.get_annual_transits(req, api_key="local")

    check("12 natal cusps", len(out["cusps"]) == 12)
    check("year ends 365 days later", out["end_instant"].startswith("2027-09-13"), out["end_instant"])

    sun = out["sun_conjunctions"]
    check("all five Sun targets answered", set(sun) == set(server.ANNUAL_SUN_TARGET_KEYS))
    check("Sun conjunct natal Sun is the solar return (Jan 1)", sun["sun"]["date"].startswith("2027-01-01"), sun["sun"]["date"])
    check("Sun conjunct Ascendant lands in the Ascendant's sign", sun["ascendant"]["sign"] == "Aries", sun["ascendant"]["sign"])
    # A natal angle's own longitude sits exactly ON its cusp, so a cusp lookup
    # there is float-ambiguous (12 vs 1); the app fixes angle rows to houses
    # 1/4/7/10 by definition and uses the stored natal Sun house for the Sun.
    check("Sun conjunction rows still carry a natal house lookup",
          all(1 <= v["natal_house"] <= 12 for v in sun.values()))
    check("every Sun conjunction is inside the following year",
          all("2026-09-13" < v["date"] < "2027-09-14" for v in sun.values()))

    ecl = [(e["kind"], e["type"], e["date"][:10], e["sign"]) for e in out["eclipses"]]
    check("five eclipses in the year", len(ecl) == 5, str(ecl))
    check("annular solar eclipse 2027-02-06 in Aquarius (template: 2/7/27 Aquarius Solar)",
          ("solar", "annular", "2027-02-06", "Aquarius") in ecl)
    check("penumbral lunar eclipse 2027-02-20 in Virgo (template: 2/21/27 Virgo Lunar)",
          ("lunar", "penumbral", "2027-02-20", "Virgo") in ecl)
    check("lunar eclipse 2027-07-18 in Capricorn (template: 7/19/27 Capricorn Lunar)",
          any(k == "lunar" and d == "2027-07-18" and s == "Capricorn" for k, _, d, s in ecl))
    check("total solar eclipse 2027-08-02 in Leo (template: 8/2/27 Leo Solar)",
          ("solar", "total", "2027-08-02", "Leo") in ecl)
    check("eclipses sorted by instant", [e["jd"] for e in out["eclipses"]] == sorted(e["jd"] for e in out["eclipses"]))
    check("eclipse rows carry a natal house", all(1 <= e["natal_house"] <= 12 for e in out["eclipses"]))

    retro = {(p["body"], p["start"]["date"][:10]): p for p in out["retrogrades"]}
    check("Saturn retrograde 2026-07-26 → 2026-12-10 (template)",
          ("saturn", "2026-07-26") in retro and retro[("saturn", "2026-07-26")]["end"]["date"].startswith("2026-12-10"))
    check("Uranus retrograde 2026-09-10 → 2027-02-08 (template)",
          ("uranus", "2026-09-10") in retro and retro[("uranus", "2026-09-10")]["end"]["date"].startswith("2027-02-08"))
    check("Neptune retrograde 2026-07-07 → 2026-12-12 (template)",
          ("neptune", "2026-07-07") in retro and retro[("neptune", "2026-07-07")]["end"]["date"].startswith("2026-12-12"))
    check("Pluto retrograde already under way at the start is included (2026-05-06, template)",
          ("pluto", "2026-05-06") in retro)
    check("Venus retrograde 2026-10-03 in Scorpio (template)",
          ("venus", "2026-10-03") in retro and retro[("venus", "2026-10-03")]["start"]["sign"] == "Scorpio")
    check("Mercury retrograde 2026-10-24 in Scorpio (template)", ("mercury", "2026-10-24") in retro)
    check("Jupiter retrograde 2026-12-13 in Leo (template: 12/12/26 Leo)",
          ("jupiter", "2026-12-13") in retro and retro[("jupiter", "2026-12-13")]["start"]["sign"] == "Leo")
    check("Mars retrograde 2027-01-10 Virgo → 2027-04-01 Leo (template: 1/10/27 – 3/31/27)",
          ("mars", "2027-01-10") in retro and retro[("mars", "2027-01-10")]["end"]["sign"] == "Leo")
    check("no retrograde period that ended before the year start",
          all(p["end"] is None or p["end"]["date"] > "2026-09-13" for p in out["retrogrades"]))
    check("no retrograde period that starts after the year end",
          all(p["start"]["date"] < "2027-09-14" for p in out["retrogrades"]))
    check("retrograde periods sorted by start", [p["start"]["jd"] for p in out["retrogrades"]] == sorted(p["start"]["jd"] for p in out["retrogrades"]))

    signs = {s["body"]: s for s in out["sign_transitions"]}
    check("five outer planets", set(signs) == set(server.ANNUAL_INGRESS_BODIES))
    check("Jupiter in Leo since 2026-06-30, next Virgo 2027-07-26 (template: 6/29/26 → 7/25/27)",
          signs["jupiter"]["current"]["sign"] == "Leo" and signs["jupiter"]["current"]["date"].startswith("2026-06-30")
          and signs["jupiter"]["next"]["sign"] == "Virgo" and signs["jupiter"]["next"]["date"].startswith("2027-07-26"))
    check("Saturn in Aries since 2026-02-14, next Taurus 2028-04 (template: 2/13/26 → Taurus)",
          signs["saturn"]["current"]["sign"] == "Aries" and signs["saturn"]["current"]["date"].startswith("2026-02-1")
          and signs["saturn"]["next"]["sign"] == "Taurus" and signs["saturn"]["next"]["date"].startswith("2028-04"))
    check("Uranus in Gemini since 2026-04-26, next Cancer 2032-08-03 (template: 4/25/26 → 8/3/32)",
          signs["uranus"]["current"]["sign"] == "Gemini" and signs["uranus"]["current"]["date"].startswith("2026-04-2")
          and signs["uranus"]["next"]["date"].startswith("2032-08-03"))
    check("Neptune in Aries since 2026-01-26, next Taurus 2038-05-22 (template: 1/26/26 → 5/21/38)",
          signs["neptune"]["current"]["date"].startswith("2026-01-26") and signs["neptune"]["next"]["date"].startswith("2038-05-2"))
    check("Pluto in Aquarius since 2024-11-19, next Pisces 2043-03-09 (template: 11/19/24 → 3/8/43)",
          signs["pluto"]["current"]["date"].startswith("2024-11-19") and signs["pluto"]["next"]["sign"] == "Pisces"
          and signs["pluto"]["next"]["date"].startswith("2043-03-0"))
    check("the current-sign entry is the LAST ingress into it (Pluto's 2023/2024 dips are not it)",
          signs["pluto"]["current"]["date"] > "2024-06-01")
    check("next rows carry the sign left", all(s["next"]["from"] == s["current"]["sign"] for s in out["sign_transitions"]))
    check("every transition placement has a natal house",
          all(1 <= s[k]["natal_house"] <= 12 for s in out["sign_transitions"] for k in ("current", "next")))

    # The station helper extraction must leave /api/stations unchanged.
    st = server.get_stations(server.StationsRequest(
        bodies=["mercury"], start_date="2026-09-01", end_date="2026-12-31"), api_key="local")
    check("/api/stations still returns Mercury's autumn pair", st["count"] == 2 and st["stations"][0]["type"] == "retrograde")
    check("/api/stations rows keep their shape",
          set(st["stations"][0]) == {"body", "date", "jd", "longitude", "sign", "degree", "type"})

    # Validation
    try:
        server.AnnualTransitsRequest(start_instant="2026-09-13T07:00:00", sun_targets={"moon": 10.0}, **FIXTURE_BIRTH)
        check("unknown sun target rejected", False)
    except Exception:
        check("unknown sun target rejected", True)
    try:
        server.AnnualTransitsRequest(start_instant="2026-09-13T07:00:00", span_days=900, sun_targets={"sun": 10.0}, **FIXTURE_BIRTH)
        check("span over 400 days rejected", False)
    except Exception:
        check("span over 400 days rejected", True)

    print()
    if failures:
        print(f"{len(failures)} FAILED: {failures}")
        raise SystemExit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()

"""Offline verification of /api/return-chart and the first-pass return rule.

Run from the repo root:  API_KEY=test .venv/bin/python test_return_chart.py

Calls the endpoint functions directly (no HTTP) and asserts against
independently known ephemeris facts. Fixture birth data is synthetic (no real
person): 1990-01-01 12:00, New York — the chart the other report tests use.
"""
import swisseph as swe
from fastapi import HTTPException

import server

FIXTURE_BIRTH = dict(
    birth_year=1990, birth_month=1, birth_day=1, birth_hour=12, birth_min=0,
    lat=40.7128, lon=-74.0060, house_type="placidus",
)
ALL = list(server.INGRESS_PLANET_IDS.keys())
OUTER = ["jupiter", "saturn", "uranus", "neptune", "pluto"]
INNER = ["sun", "moon", "mercury", "venus", "mars"]
ASPECTS = {"Sextile": 60.0, "Square": 90.0, "Trine": 120.0, "Opposition": 180.0}


def natal_positions():
    bjd = server.calculate_julian_day(1990, 1, 1, 12, 0, 40.7128, -74.0060)
    return {body: server.get_transit_lon(bjd, pid) for body, pid in server.INGRESS_PLANET_IDS.items()}


NATAL = natal_positions()


def iso_jd(iso: str) -> float:
    y, m, d = int(iso[0:4]), int(iso[5:7]), int(iso[8:10])
    hh, mm, ss = int(iso[11:13]), int(iso[14:16]), int(iso[17:19])
    return swe.julday(y, m, d, hh + mm / 60.0 + ss / 3600.0, swe.GREG_CAL)


def run(body, mode, anchor, transiting=OUTER, targets=INNER):
    request = server.ReturnChartRequest(
        **FIXTURE_BIRTH, anchor_instant=anchor, body=body, period_mode=mode,
        natal_positions=NATAL, transiting_bodies=transiting, natal_targets=targets,
        transit_aspects=ASPECTS,
    )
    return server.get_return_chart(request, "test")


def main():
    failures = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")
        if not cond:
            failures.append(name)

    print("group_return_passes")
    events = server.group_return_passes([0.0, 10.0, 30.0, 400.0, 765.0], 365.26)
    check("passes within half a period are one return", events == [[0.0, 10.0, 30.0], [400.0], [765.0]], str(events))

    print("Mercury — retrograde triple pass")
    for anchor in ("2021-12-31T19:00:00", "2022-06-01T19:00:00", "2022-12-31T19:00:00"):
        out = run("mercury", "current", anchor)
        check(f"anchor {anchor[:10]}: return = FIRST of three passes",
              out["return"]["moment"].startswith("2021-12-30") and len(out["return"]["passes"]) == 3,
              out["return"]["moment"])
    moment_lon = server.get_transit_lon(iso_jd(out["return"]["moment"]), swe.MERCURY)
    check("Mercury sits on its natal degree at the moment",
          abs(server.angle_separation(moment_lon, NATAL["mercury"])) < 0.001)
    check("period ends at the next return's first pass", out["period"]["end"].startswith("2023-02-08"))

    print("Solar")
    out = run("sun", "current", "2026-10-11T19:00:00")
    check("solar return on the birthday", out["return"]["moment"].startswith("2026-01-01"), out["return"]["moment"])
    days = iso_jd(out["period"]["end"]) - iso_jd(out["period"]["start"])
    check("solar period is one year", 364.5 < days < 366.5, f"{days:.2f}d")
    check("birthplace time zone returned", out["time_zone"] == "America/New_York", out["time_zone"])
    check("return chart carries 12 house cusps", len(out["chart"]["houses"]) == 12)

    print("Lunar — New Moon window")
    anchor = "2026-10-11T19:00:00"
    out = run("moon", "lunation", anchor, ALL, ALL)
    start, end = iso_jd(out["period"]["start"]), iso_jd(out["period"]["end"])
    for label, jd in (("start", start), ("end", end)):
        elong = server.angle_separation(server.get_transit_lon(jd, swe.MOON), server.get_transit_lon(jd, swe.SUN))
        check(f"window {label} is a new moon", elong < 0.05, f"{elong:.4f}°")
    check("window contains the anchor", start <= iso_jd(anchor) < end)
    m = iso_jd(out["return"]["moment"])
    check("lunar return inside the window", start <= m < end)
    check("Moon on its natal degree at the moment",
          server.angle_separation(server.get_transit_lon(m, swe.MOON), NATAL["moon"]) < 0.001)
    try:
        run("sun", "lunation", anchor)
        check("lunation refused for a non-Moon body", False)
    except HTTPException as e:
        check("lunation refused for a non-Moon body", e.status_code == 422)

    print("Saturn — first pass, current and upcoming")
    out = run("saturn", "current", "2026-10-11T19:00:00")
    check("2019 return starts at the FIRST pass (Feb), not a later pass",
          out["return"]["moment"].startswith("2019-02-07") and len(out["return"]["passes"]) == 3,
          out["return"]["moment"])
    check("not upcoming once it has happened", out["return"]["upcoming"] is False)
    out = run("saturn", "current", "2000-06-01T19:00:00")
    check("before the first return the upcoming return is used",
          out["return"]["upcoming"] is True and out["return"]["moment"].startswith("2019-02-07"))

    print("Uranus — first true return (age ~84)")
    out = run("uranus", "first", "2026-10-11T19:00:00")
    year = int(out["return"]["moment"][:4])
    check("Uranus return in the early 2070s", 2072 <= year <= 2074, out["return"]["moment"])
    check("flagged upcoming", out["return"]["upcoming"] is True)

    print("Exact transits")
    out = run("saturn", "current", "2026-10-11T19:00:00")
    ps, pe = iso_jd(out["period"]["start"]), iso_jd(out["period"]["end"])
    worst = 0.0
    inside = True
    for hit in out["transits"]:
        jd = iso_jd(hit["date"])
        inside = inside and ps <= jd <= pe
        sep = server.angle_separation(
            server.get_transit_lon(jd, server.INGRESS_PLANET_IDS[hit["transiting"]]), NATAL[hit["natal"]])
        worst = max(worst, abs(sep - ASPECTS[hit["aspect"]]))
    check("every transit is exact", worst < 0.01, f"worst {worst:.5f}°")
    check("every transit falls inside the period", inside)
    check("only the requested bodies", all(h["transiting"] in OUTER and h["natal"] in INNER for h in out["transits"]))
    dates = [h["date"] for h in out["transits"]]
    check("transits in date order", dates == sorted(dates))

    print("/api/returns uses the first pass")
    request = server.ReturnsRequest(
        **FIXTURE_BIRTH, anchor_instant="2019-06-01T19:00:00", bodies=["saturn"],
        natal_positions=NATAL, current_lat=40.7128, current_lon=-74.0060,
    )
    cycle = server.get_returns(request, "test")["returns"]["saturn"]["cycle"]
    check("anchor between passes → cycle starts at the first pass",
          cycle["start"].startswith("2019-02-07") and len(cycle["start_passes"]) == 3, cycle["start"])

    if failures:
        print(f"\n{len(failures)} return-chart check(s) FAILED: {failures}")
        raise SystemExit(1)
    print("\nAll return-chart checks passed.")


if __name__ == "__main__":
    main()

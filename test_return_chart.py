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
ANGLES = dict(server.RETURN_CHART_ASPECTS_DEFAULT)


def natal_positions():
    bjd = server.calculate_julian_day(1990, 1, 1, 12, 0, 40.7128, -74.0060)
    return {body: server.get_transit_lon(bjd, pid) for body, pid in server.INGRESS_PLANET_IDS.items()}


NATAL = natal_positions()


def iso_jd(iso: str) -> float:
    y, m, d = int(iso[0:4]), int(iso[5:7]), int(iso[8:10])
    hh, mm, ss = int(iso[11:13]), int(iso[14:16]), int(iso[17:19])
    return swe.julday(y, m, d, hh + mm / 60.0 + ss / 3600.0, swe.GREG_CAL)


def run(body, mode, anchor):
    request = server.ReturnChartRequest(
        **FIXTURE_BIRTH, anchor_instant=anchor, body=body, period_mode=mode, natal_positions=NATAL,
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

    print("Lunar — the return in effect, like every type")
    anchor = "2026-10-11T19:00:00"
    out = run("moon", "current", anchor)
    start, end = iso_jd(out["period"]["start"]), iso_jd(out["period"]["end"])
    check("Lunar period is one sidereal month", 27.0 < end - start < 27.7, f"{end - start:.2f}d")
    check("period contains the anchor", start <= iso_jd(anchor) < end)
    check("Moon on its natal degree at the return",
          server.angle_separation(server.get_transit_lon(start, swe.MOON), NATAL["moon"]) < 0.001)
    try:
        server.ReturnChartRequest(**FIXTURE_BIRTH, anchor_instant=anchor, body="moon", period_mode="lunation", natal_positions=NATAL)
        check("the New Moon window mode is gone", False)
    except Exception:
        check("the New Moon window mode is gone", True)

    print("Self-aspect windows (the planet's relationship with itself)")
    out = run("sun", "current", "2026-10-11T19:00:00")
    wins = out["self_windows"]
    ps, pe = iso_jd(out["period"]["start"]), iso_jd(out["period"]["end"])
    exact_count = {}
    for w in wins:
        exact_count[w["aspect"]] = exact_count.get(w["aspect"], 0) + len(w["exacts"])
    check("Sun: 1 conjunction (the return), 2 sextiles, 2 squares, 2 trines, 1 opposition exact",
          exact_count == {"Conjunction": 1, "Sextile": 2, "Square": 2, "Trine": 2, "Opposition": 1}, str(exact_count))
    conj = [w for w in wins if w["aspect"] == "Conjunction"]
    check("conjunction in orb at the period start is clamped to the start, and its exact is the return",
          conj[0]["enter_clamped"] and conj[0]["enter"] == out["period"]["start"]
          and abs(iso_jd(conj[0]["exacts"][0]["date"]) - ps) < 3e-4)
    check("conjunction still in orb at the period end is clamped to the end, with no exact (next cycle)",
          conj[-1]["exit_clamped"] and conj[-1]["exit"] == out["period"]["end"] and conj[-1]["exacts"] == [])
    worst_exact, worst_edge, inside = 0.0, 0.0, True
    for w in wins:
        angle = ANGLES[w["aspect"]]
        for hit in w["exacts"]:
            jd = iso_jd(hit["date"])
            inside = inside and iso_jd(w["enter"]) - 1e-4 <= jd <= iso_jd(w["exit"]) + 1e-4
            worst_exact = max(worst_exact, abs(server.angle_separation(server.get_transit_lon(jd, swe.SUN), NATAL["sun"]) - angle))
        for edge, clamped in ((w["enter"], w["enter_clamped"]), (w["exit"], w["exit_clamped"])):
            if not clamped:
                sep = server.angle_separation(server.get_transit_lon(iso_jd(edge), swe.SUN), NATAL["sun"])
                worst_edge = max(worst_edge, abs(abs(sep - angle) - 8.0))
    check("every exact is exact", worst_exact < 0.01, f"worst {worst_exact:.5f}°")
    check("every exact sits inside its window", inside)
    check("window edges are the 8° orb", worst_edge < 0.01, f"worst {worst_edge:.5f}°")
    check("windows in date order", [w["enter"] for w in wins] == sorted(w["enter"] for w in wins))

    out = run("saturn", "current", "2026-10-11T19:00:00")
    check("a retrograde Saturn lists more than one exact in a window",
          any(len(w["exacts"]) > 1 for w in out["self_windows"]))
    out = run("moon", "current", "2026-10-11T19:00:00")
    check("Lunar windows are found on the hourly walk (8 exact aspects in a month)",
          sum(len(w["exacts"]) for w in out["self_windows"] if w["aspect"] != "Conjunction") == 7
          and sum(len(w["exacts"]) for w in out["self_windows"] if w["aspect"] == "Conjunction") == 1)

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

    print("/api/returns uses the first pass")
    request = server.ReturnsRequest(
        **FIXTURE_BIRTH, anchor_instant="2019-06-01T19:00:00", bodies=["saturn"],
        natal_positions=NATAL, current_lat=40.7128, current_lon=-74.0060,
    )
    cycle = server.get_returns(request, "test")["returns"]["saturn"]["cycle"]
    check("anchor between passes → cycle starts at the first pass",
          cycle["start"].startswith("2019-02-07") and len(cycle["start_passes"]) == 3, cycle["start"])

    print("Natal chart for the biwheel")
    out = run("sun", "current", "2026-10-11T19:00:00")
    natal_chart = out["natal"]["chart"]
    check("natal chart carries 12 bodies, angles and 12 cusps",
          len(natal_chart["planets"]) == 12 and len(natal_chart["houses"]) == 12 and "ascendant" in natal_chart["angles"])
    check("natal Sun on the wheel is the natal Sun",
          server.angle_separation(natal_chart["planets"]["sun"]["longitude"], NATAL["sun"]) < 0.001)

    print("Birthplace-local anchor")
    request = server.ReturnChartRequest(
        **FIXTURE_BIRTH, anchor_instant="2026-10-11T12:00:00", anchor_local=True, body="sun",
        period_mode="current", natal_positions=NATAL,
    )
    out = server.get_return_chart(request, "test")
    check("noon New York (EDT) is 16:00 UT",
          abs(iso_jd(out["anchor_ut"]) - swe.julday(2026, 10, 11, 16.0, swe.GREG_CAL)) < 2 / 86400.0, out["anchor_ut"])

    if failures:
        print(f"\n{len(failures)} return-chart check(s) FAILED: {failures}")
        raise SystemExit(1)
    print("\nAll return-chart checks passed.")


if __name__ == "__main__":
    main()

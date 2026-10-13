"""Offline verification of /api/ingresses and the widened /api/transits.

Run from the repo root:  .venv/bin/python test_ingresses.py

Calls the endpoint functions directly (no HTTP, no API key) and asserts
against independently known ephemeris facts. Fixture birth data is synthetic
(no real person): 1990-01-01 12:00, New York.
"""
import server

FIXTURE_BIRTH = dict(
    birth_year=1990, birth_month=1, birth_day=1, birth_hour=12, birth_min=0,
    lat=40.7128, lon=-74.0060, house_type="P",
)


def run_ingresses(**overrides):
    req = server.IngressRequest(
        start_date="2026-09-09", end_date="2026-11-09",
        bodies=["sun", "moon", "mercury"], **FIXTURE_BIRTH, **overrides,
    )
    return server.get_ingresses(req, api_key="local")


def main():
    failures = []

    def check(name, cond, detail=""):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {name} {detail}")
        if not cond:
            failures.append(name)

    print("== /api/ingresses: 2026-09-09 .. 2026-11-09, sun/moon/mercury ==")
    out = run_ingresses()

    check("12 natal cusps", len(out["cusps"]) == 12, str(out["cusps"][:3]))
    check("positions carry all requested bodies",
          set(out["positions"]) == {"sun", "moon", "mercury"})
    sun_pos = out["positions"]["sun"]
    check("Sun in Virgo on 2026-09-09", sun_pos["sign"] == "Virgo", sun_pos["sign"])
    check("Sun never retrograde", sun_pos["retrograde"] is False)

    sun_signs = [e for e in out["events"] if e["body"] == "sun" and e["type"] == "sign"]
    check("Sun makes exactly 2 sign ingresses in 2 months", len(sun_signs) == 2,
          str([(e["from"], e["to"], e["date"]) for e in sun_signs]))
    libra = next((e for e in sun_signs if e["to"] == "Libra"), None)
    check("Sun Virgo->Libra (equinox) on Sep 22-23",
          libra is not None and libra["from"] == "Virgo"
          and libra["date"][:10] in ("2026-09-22", "2026-09-23"),
          libra["date"] if libra else "missing")

    moon_signs = [e for e in out["events"] if e["body"] == "moon" and e["type"] == "sign"]
    check("Moon sign ingresses in 61 days ~ 25-29", 25 <= len(moon_signs) <= 29,
          str(len(moon_signs)))
    seq_ok = all(
        (server.SIGNS.index(e["to"]) - server.SIGNS.index(e["from"])) % 12 == 1
        for e in moon_signs)
    check("every Moon ingress steps one sign forward", seq_ok)

    # Known retrograde boundary crossing: Mercury retrograde re-entered
    # Scorpio from Sagittarius on 2025-11-19 (its 2026 retrogrades all stay
    # inside one sign, so 2025 is the deterministic fixture year).
    wide = server.get_ingresses(server.IngressRequest(
        start_date="2025-11-01", end_date="2025-12-15",
        bodies=["mercury"], **FIXTURE_BIRTH), api_key="local")
    merc = [e for e in wide["events"] if e["type"] == "sign"]
    retro_cross = [e for e in merc if e["retrograde"]]
    check("Mercury retrograde Sagittarius->Scorpio on 2025-11-19",
          any(e["from"] == "Sagittarius" and e["to"] == "Scorpio"
              and e["date"][:10] in ("2025-11-18", "2025-11-19") for e in retro_cross),
          str([(e["from"], e["to"], e["date"], e["retrograde"]) for e in merc]))

    house_events = [e for e in out["events"] if e["type"] == "house"]
    check("house crossings occur", len(house_events) > 0, f"{len(house_events)} events")
    hseq_ok = all(isinstance(e["from"], int) and isinstance(e["to"], int)
                  and 1 <= e["from"] <= 12 and 1 <= e["to"] <= 12 for e in house_events)
    check("house events carry house numbers 1-12", hseq_ok)

    # Events are chronological
    jds = [e["jd"] for e in out["events"]]
    check("events chronological", jds == sorted(jds))

    print("== /api/transits: transiting Sun conjunct longitude 180.0 ==")
    treq = server.TransitRequest(
        natal_positions={"probe": 180.0},
        start_date="2026-09-01", end_date="2026-10-15",
        **FIXTURE_BIRTH,
        transiting_planets=["sun"],
        aspects={"Conjunction": {"angle": 0, "orb": 1.0}},
        step_days=1,
    )
    tout = server.get_transits(treq, api_key="local")
    hits = tout["transits"]
    check("exactly one Sun conjunction to 180.0", len(hits) == 1, str(hits))
    if len(hits) == 1:
        check("conjunction lands on the Libra ingress date (Sun at 180.0)",
              str(hits[0].get("date", hits[0]))[:10] in ("2026-09-22", "2026-09-23"),
              str(hits[0])[:200])

    print("== /api/longitudes: noon positions for the daily-orb derivation ==")
    lreq = server.LongitudesRequest(
        instants=["2026-09-22T19:00:00", "2026-03-20T15:00:00"],
        bodies=["sun", "moon"],
    )
    lout = server.get_longitudes(lreq, api_key="local")
    check("one entry per instant", len(lout["longitudes"]) == 2, str(lout["count"]))
    equinox_sun = lout["longitudes"]["2026-09-22T19:00:00"]["sun"]
    check("Sun just shy of 180.0 five hours before the 2026 Libra ingress (00:05 UT Sep 23)",
          179.7 < equinox_sun < 180.0)
    march_sun = lout["longitudes"]["2026-03-20T15:00:00"]["sun"]
    check("Sun ~0.0/360 near the 2026 Aries ingress (equinox ~14:46 UT)",
          march_sun < 0.2 or march_sun > 359.8)
    check("every longitude in [0,360)",
          all(0 <= lon < 360 for by_body in lout["longitudes"].values() for lon in by_body.values()))

    print()
    if failures:
        print(f"FAILURES: {failures}")
        raise SystemExit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()

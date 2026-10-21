"""Send the same synthetic requests to two running servers and diff the JSON.

Used to prove a dependency upgrade changes no chart output:

  API_KEY=k .venv-old/bin/uvicorn server:app --port 8101 &
  API_KEY=k .venv-new/bin/uvicorn server:app --port 8102 &
  python3 http_parity.py http://127.0.0.1:8101 http://127.0.0.1:8102 k

Every endpoint gets one valid request (synthetic birth data, no real person: 1990-01-01 12:00,
New York, the fixture the other tests use) plus three that must be refused: no key, a wrong key
and an invalid body. Exits non-zero on any status or body difference. Plain urllib so it runs
outside either virtualenv. For a Cloud Run server, put an identity token in PARITY_ID_TOKEN
(`gcloud auth print-identity-token`); it is sent to any https base URL.
"""
import json
import os
import sys
import urllib.error
import urllib.request

BIRTH = dict(birth_year=1990, birth_month=1, birth_day=1, birth_hour=12, birth_min=0,
             lat=40.7128, lon=-74.0060, house_type="placidus")
CHART = dict(year=1990, month=1, day=1, hour=12, min=0, lat=40.7128, lon=-74.0060)
ASPECTS = {"Conjunction": {"angle": 0, "orb": 1.0}, "Square": {"angle": 90, "orb": 1.0}}


def call(base, path, body=None, key=None):
    headers = {"Content-Type": "application/json", **({"X-API-Key": key} if key else {})}
    if base.startswith("https://") and os.environ.get("PARITY_ID_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['PARITY_ID_TOKEN']}"
    req = urllib.request.Request(base + path, method="POST" if body is not None else "GET",
                                 data=None if body is None else json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=300) as res:
            return res.status, json.loads(res.read() or b"null")
    except urllib.error.HTTPError as err:
        return err.code, None  # error bodies differ in wording across FastAPI versions; status is the contract


def requests(natal):
    return [
        ("/", None),
        ("/api/planets", CHART),
        ("/api/houses", CHART),
        ("/api/chart", CHART),
        ("/api/transits", dict(BIRTH, natal_positions=natal, start_date="2026-01-01", end_date="2026-12-31")),
        ("/api/stations", dict(start_date="2026-01-01", end_date="2026-12-31")),
        ("/api/ingresses", dict(BIRTH, start_date="2026-01-01", end_date="2026-12-31")),
        ("/api/orb-windows", dict(start_date="2026-01-01", end_date="2026-03-31", natal_positions=natal, aspects=ASPECTS)),
        ("/api/longitudes", dict(instants=["2026-09-13T19:00:00", "2026-10-24T12:00:00"])),
        ("/api/returns", dict(BIRTH, anchor_instant="2026-10-24T12:00:00", natal_positions=natal,
                              current_lat=40.7128, current_lon=-74.0060, self_aspects={"Square": 90, "Opposition": 180})),
        ("/api/return-chart", dict(BIRTH, anchor_instant="2026-10-24T12:00:00", body="sun", natal_positions=natal,
                                   aspects={"Conjunction": 0, "Square": 90})),
        ("/api/monthly-transits", dict(start_instant="2026-10-01T07:00:00")),
        ("/api/annual-transits", dict(BIRTH, start_instant="2026-09-13T07:00:00", sun_targets={"sun": natal["sun"]})),
        ("/api/lifetime-returns", dict(BIRTH, natal_positions=natal)),
    ]


def main(a, b, key):
    status, planets = call(a, "/api/planets", CHART, key)
    assert status == 200, status
    natal = {name: v["longitude"] for name, v in planets.items() if isinstance(v, dict) and "longitude" in v}
    failures = 0
    for path, body in requests(natal):
        cases = [("valid", body, key)]
        if body is not None:
            cases += [("no key", body, None), ("wrong key", body, "wrong"), ("invalid body", {"bogus": 1}, key)]
        for label, payload, k in cases:
            ra, rb = call(a, path, payload, k), call(b, path, payload, k)
            same = ra == rb
            ok = same and (ra[0] == 200 if label == "valid" else ra[0] in (403, 422))
            failures += not ok
            print(f"{'ok  ' if ok else 'FAIL'} {path} {label}: {ra[0]} vs {rb[0]}{'' if same else ' (bodies differ)'}")
    print(f"\n{failures} failed" if failures else "\nALL MATCH")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))

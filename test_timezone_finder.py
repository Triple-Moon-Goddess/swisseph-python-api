"""
TimezoneFinder is built once per process, not per request, and lookups stay
correct when the thread pool runs them at the same time.

Run from the repo root:  .venv/bin/python test_timezone_finder.py

Building a TimezoneFinder reads its data files (about 0.4 s in the prod
image). Before this change /api/planets, /api/chart and every call that turns
a birth time into UT built a new one. The constructor is wrapped before
server is imported, so every construction is counted. Fixture points are
cities, not people.
"""
import os
import sys
import threading

os.environ.setdefault("AUTH_MODE", "cloud-run-iam")
os.environ.pop("API_KEY", None)

import timezonefinder

constructed = []
_RealTimezoneFinder = timezonefinder.TimezoneFinder


class CountingTimezoneFinder(_RealTimezoneFinder):
    def __init__(self, *args, **kwargs):
        constructed.append(1)
        super().__init__(*args, **kwargs)


timezonefinder.TimezoneFinder = CountingTimezoneFinder

from fastapi.testclient import TestClient

import server

client = TestClient(server.app)

passes = failures = 0


def check(name, ok, detail=""):
    global passes, failures
    if ok:
        passes += 1
        print(f"  PASS {name}")
    else:
        failures += 1
        print(f"  FAIL {name} {detail}")


POINTS = {
    (40.7128, -74.0060): "America/New_York",
    (51.5074, -0.1278): "Europe/London",
    (35.6762, 139.6503): "Asia/Tokyo",
    (-33.8688, 151.2093): "Australia/Sydney",
    (19.4326, -99.1332): "America/Mexico_City",
    (-23.5505, -46.6333): "America/Sao_Paulo",
}

print("1. built once at import")
check("one TimezoneFinder after import", len(constructed) == 1, f"got {len(constructed)}")

print("\n2. lookups are correct")
for (lat, lon), zone in POINTS.items():
    check(f"{zone}", server.timezone_at(lat, lon) == zone, server.timezone_at(lat, lon))

print("\n3. requests reuse it")
for _ in range(5):
    server.calculate_julian_day(1990, 1, 1, 12, 0, 40.7128, -74.0060)
chart = dict(year=1990, month=1, day=1, hour=12, min=0, lat=40.7128, lon=-74.0060)
for _ in range(3):
    r = client.post("/api/planets", json=chart)
check("/api/planets answers 200", r.status_code == 200, r.status_code)
check("still one TimezoneFinder after 5 conversions and 3 requests",
      len(constructed) == 1, f"got {len(constructed)}")
check("New York birth time converted to UT (EST, +5 h)",
      abs(server.calculate_julian_day(1990, 1, 1, 12, 0, 40.7128, -74.0060)
          - server.swe.julday(1990, 1, 1, 17.0, server.swe.GREG_CAL)) < 1e-9)

print("\n4. concurrent lookups from 8 threads")
wrong = []
start = threading.Barrier(8)


def worker():
    start.wait()
    for _ in range(100):
        for (lat, lon), zone in POINTS.items():
            got = server.timezone_at(lat, lon)
            if got != zone:
                wrong.append((zone, got))


threads = [threading.Thread(target=worker) for _ in range(8)]
for t in threads:
    t.start()
for t in threads:
    t.join()
check("4,800 concurrent lookups all correct", not wrong, wrong[:3])

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)

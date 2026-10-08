"""Birth data never reaches the logs, and the API key check has no default.

Run from the repo root:  .venv/bin/python test_no_birth_data_in_logs.py

Calls the chart endpoints directly (no HTTP) with synthetic birth data (no real
person: 1987-03-14 06:42, lat 12.3456, lon 65.4321), captures everything the
process logs or prints, and asserts none of it carries the birth date, time,
place, or a planet longitude for that instant. Then checks verify_api_key
refuses no key, a wrong key and the old well-known placeholder, and accepts the
configured key.
"""
import asyncio
import contextlib
import io
import logging
import os

os.environ.setdefault("API_KEY", "probe-test-key")
import server  # noqa: E402  (API_KEY must be set before import: no default)
from fastapi import HTTPException  # noqa: E402

BIRTH = dict(year=1987, month=3, day=14, hour=6, min=42, lat=12.3456, lon=65.4321)
LEAKS = ["1987-3-14", "1987-03-14", "1987", "12.3456", "65.4321", "longitude="]


def capture(fn):
    """Run fn; return (result, everything logged or printed meanwhile)."""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            result = fn()
    finally:
        root.removeHandler(handler)
    return result, buf.getvalue()


def main():
    failures = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")
        if not cond:
            failures.append(name)

    req = server.ChartRequest(**BIRTH)
    for name, fn in [("planets", server.get_planets), ("houses", server.get_houses), ("chart", server.get_chart)]:
        result, out = capture(lambda: fn(req, api_key="probe-test-key"))
        leaked = [s for s in LEAKS if s in out]
        check(f"/api/{name} logs no birth data", not leaked, f"(leaked: {leaked})" if leaked else "")
        check(f"/api/{name} still computes", bool(result))

    def key_result(key):
        try:
            asyncio.run(server.verify_api_key(key))
            return "accepted"
        except HTTPException as e:
            return e.status_code

    check("no key is refused", key_result(None) == 403)
    check("a wrong key is refused", key_result("wrong") == 403)
    check("the old placeholder key is refused", key_result("your-secret-key-here") == 403)
    check("the configured key is accepted", key_result("probe-test-key") == "accepted")

    print(f"\n{'ALL PASS' if not failures else f'{len(failures)} FAILED'}")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()

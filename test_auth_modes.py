"""
Caller authentication: the server never comes up open by accident.

Run from the repo root:  .venv/bin/python test_auth_modes.py

Each case starts a fresh Python with its own environment, imports server, and
calls an endpoint through FastAPI's TestClient:
  1. Neither API_KEY nor AUTH_MODE set: the server refuses to start.
  2. AUTH_MODE set to anything but cloud-run-iam: refuses to start.
  3. API_KEY set: a request with no key or a wrong key gets 403; the right key
     gets through.
  4. AUTH_MODE=cloud-run-iam, no API_KEY: a request with no key gets through
     (Cloud Run IAM is the gate in front of the process).
  5. Both set: API_KEY wins and the key is still required.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

PROBE = r"""
import json, sys
try:
    import server
except RuntimeError as e:
    print(json.dumps({"started": False, "error": str(e)}))
    sys.exit(0)
from fastapi.testclient import TestClient
c = TestClient(server.app)
body = {"date": "2000-01-01", "time": "12:00", "latitude": 0, "longitude": 0, "timezone": "UTC"}
out = {"started": True}
for name, headers in [("none", {}), ("wrong", {"X-API-Key": "wrong"}), ("right", {"X-API-Key": "right-key"})]:
    out[name] = c.post("/api/planets", json=body, headers=headers).status_code
print(json.dumps(out))
"""


def run(env_overrides):
    env = {k: v for k, v in os.environ.items() if k not in ("API_KEY", "AUTH_MODE")}
    env.update(env_overrides)
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=HERE, env=env, capture_output=True, text=True)
    last = (r.stdout.strip().splitlines() or ["{}"])[-1]
    try:
        return json.loads(last)
    except ValueError:
        return {"started": None, "stderr": r.stderr[-400:]}


passes = failures = 0


def check(name, cond, detail=""):
    global passes, failures
    passes, failures = passes + bool(cond), failures + (not cond)
    print(f"  {'✓' if cond else '✗'} {name}{f'  ({detail})' if detail and not cond else ''}")


print("\n1. nothing configured")
r = run({})
check("refuses to start", r.get("started") is False and "Refusing to start open" in r.get("error", ""), r)

print("\n2. unknown AUTH_MODE")
r = run({"AUTH_MODE": "open"})
check("refuses to start", r.get("started") is False, r)

print("\n3. API_KEY")
r = run({"API_KEY": "right-key"})
check("starts", r.get("started") is True, r)
check("no key → 403", r.get("none") == 403, r)
check("wrong key → 403", r.get("wrong") == 403, r)
check("right key → admitted (not 403)", r.get("right") not in (None, 403), r)

print("\n4. AUTH_MODE=cloud-run-iam")
r = run({"AUTH_MODE": "cloud-run-iam"})
check("starts", r.get("started") is True, r)
check("no key → admitted (not 403)", r.get("none") not in (None, 403), r)

print("\n5. both set")
r = run({"API_KEY": "right-key", "AUTH_MODE": "cloud-run-iam"})
check("no key → 403 (API_KEY wins)", r.get("none") == 403, r)
check("right key → admitted", r.get("right") not in (None, 403), r)

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)

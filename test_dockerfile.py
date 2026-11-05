"""
test_dockerfile.py — the container image runs as a non-root user from a pinned base.

Run from the repo root:  .venv/bin/python test_dockerfile.py
"""
import re
import sys

failures = 0


def ok(cond, msg):
    global failures
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        failures += 1


lines = [l.strip() for l in open("Dockerfile", encoding="utf-8") if l.strip() and not l.strip().startswith("#")]
froms = [l for l in lines if l.upper().startswith("FROM ")]
ok(len(froms) == 1 and re.search(r"@sha256:[0-9a-f]{64}$", froms[0]) is not None, "the base image is pinned by digest")
users = [l.split(None, 1)[1] for l in lines if l.upper().startswith("USER ")]
ok(bool(users) and users[-1] not in ("root", "0"), "the last USER is not root")
user_at = max((i for i, l in enumerate(lines) if l.upper().startswith("USER ")), default=-1)
cmd_at = max((i for i, l in enumerate(lines) if l.upper().startswith("CMD ")), default=-1)
ok(user_at < cmd_at, "USER is set before the server starts")
ok(any("chown" in l and "/app/ephe" in l for l in lines), "the unprivileged user owns /app/ephe, where startup downloads asteroid files")
ok(not any("chown" in l and re.search(r"/app(\s|$)", l) for l in lines), "the code folder itself stays root-owned")

print(f"\n{'FAIL' if failures else 'PASS'}: {failures} failure(s)")
sys.exit(1 if failures else 0)

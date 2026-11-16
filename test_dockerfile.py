"""
test_dockerfile.py — the image runs as a non-root user from a digest-pinned base (SOP 56 §2).

Checks the Dockerfile itself, and, when run inside the built image (SOP 57 §2), the user the
process actually runs as.
Run from the repo root:  python test_dockerfile.py
"""
import os
import re
import sys

failures = 0


def ok(cond, msg):
    global failures
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        failures += 1


here = os.path.dirname(os.path.abspath(__file__))
dockerfile = os.path.join(here, "Dockerfile")
if os.path.exists(dockerfile):
    lines = [l.strip() for l in open(dockerfile, encoding="utf-8") if l.strip() and not l.strip().startswith("#")]
    froms = [l for l in lines if l.upper().startswith("FROM ")]
    ok(len(froms) == 1 and re.search(r"@sha256:[0-9a-f]{64}$", froms[0]) is not None, "the base image is pinned by digest")
    users = [l.split(None, 1)[1] for l in lines if l.upper().startswith("USER ")]
    ok(bool(users) and users[-1] not in ("root", "0"), "the last USER is not root")
    user_at = max((i for i, l in enumerate(lines) if l.upper().startswith("USER ")), default=-1)
    cmd_at = max((i for i, l in enumerate(lines) if l.upper().startswith("CMD ")), default=-1)
    ok(0 <= user_at < cmd_at, "USER is set before the server starts")
    ok(any("chown" in l and "/app/ephe" in l for l in lines), "the unprivileged user owns /app/ephe, where startup may refill asteroid files")
    ok(not any("chown" in l and re.search(r"/app(\s|$)", l) for l in lines), "the code folder itself stays root-owned")
    test_lines = [l.strip() for l in open(os.path.join(here, "Dockerfile.test"), encoding="utf-8") if l.strip().upper().startswith("FROM PYTHON")]
    ok(all("@sha256:" in l for l in test_lines), "the test-tools stage is pinned too")
else:
    # Inside the image there is no Dockerfile: check the running process instead.
    ok(os.geteuid() != 0, f"the server's user is not root (uid {os.geteuid()})")
    ok(os.access("/app/ephe", os.W_OK), "it can write /app/ephe (the startup downloader's folder)")
    ok(not os.access("/app/server.py", os.W_OK), "it cannot change the server code")
    ok(not os.access("/usr/local/lib/python3.11/site-packages", os.W_OK), "it cannot change the installed packages")

print(f"\n{'FAIL' if failures else 'PASS'}: {failures} failure(s)")
sys.exit(1 if failures else 0)

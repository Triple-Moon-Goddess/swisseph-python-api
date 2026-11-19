"""
test_dockerfile.py — the image runs as a non-root user from a digest-pinned base, with no setuid
or setgid file (SOP 56 §2; CIS Docker Benchmark v1.6.0 4.8).

Checks the Dockerfile itself, and, when run inside the built image (SOP 57 §2), the user the
process actually runs as.
Run from the repo root:  python test_dockerfile.py
"""
import os
import re
import stat
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
    strip_at = [i for i, l in enumerate(lines) if l.upper().startswith("RUN ") and "-perm /6000" in l and "chmod a-s" in l and "-xdev" in l]
    writes = [i for i, l in enumerate(lines) if l.split(None, 1)[0].upper() in ("RUN", "COPY", "ADD")]
    ok(len(strip_at) == 1, "one step clears every setuid and setgid bit (find / -xdev -perm /6000 ... chmod a-s)")
    ok(len(strip_at) == 1 and writes and strip_at[0] == writes[-1], "it is the last step that writes files, so nothing after it adds a bit back")
    ok(len(strip_at) == 1 and strip_at[0] < user_at, "it runs before the switch to uid 10001, as root")
    test_lines = [l.strip() for l in open(os.path.join(here, "Dockerfile.test"), encoding="utf-8") if l.strip().upper().startswith("FROM PYTHON")]
    ok(all("@sha256:" in l for l in test_lines), "the test-tools stage is pinned too")
else:
    # Inside the image there is no Dockerfile: check the running process instead.
    ok(os.geteuid() != 0, f"the server's user is not root (uid {os.geteuid()})")
    ok(os.access("/app/ephe", os.W_OK), "it can write /app/ephe (the startup downloader's folder)")
    ok(not os.access("/app/server.py", os.W_OK), "it cannot change the server code")
    ok(not os.access("/usr/local/lib/python3.11/site-packages", os.W_OK), "it cannot change the installed packages")
    # CIS 4.8, as this user sees the image. Folders it cannot read are covered by the root find
    # in scripts/image.sh build, which fails the build on any setuid or setgid file.
    root_dev, found, unreadable = os.lstat("/").st_dev, [], []
    for d, subdirs, files in os.walk("/", onerror=lambda e: unreadable.append(e.filename)):
        subdirs[:] = [s for s in subdirs if os.lstat(os.path.join(d, s)).st_dev == root_dev]
        for f in files:
            try:
                st = os.lstat(os.path.join(d, f))
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode) and st.st_mode & (stat.S_ISUID | stat.S_ISGID):
                found.append(os.path.join(d, f))
    ok(not found, f"no setuid or setgid file in the image (found: {found}; {len(unreadable)} folder(s) unreadable as this user, checked by the root find)")

print(f"\n{'FAIL' if failures else 'PASS'}: {failures} failure(s)")
sys.exit(1 if failures else 0)

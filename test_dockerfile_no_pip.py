"""
test_dockerfile_no_pip.py — the image keeps no pip (risk register R-003).

pip is used once, to install requirements.txt; the server, download_asteroids.py and
uvicorn never import it. The install step removes setuptools, wheel and pip, deletes the
pip wheel ensurepip bundles, and fails the build if pip can still be imported. Nothing
after that step may install or call pip again.

Run from the repo root:  python3 test_dockerfile_no_pip.py
"""
import re
import sys

failures = 0


def ok(cond, msg):
    global failures
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        failures += 1


text = open("Dockerfile", encoding="utf-8").read()
# One logical line per instruction: join backslash continuations, drop comments.
joined = re.sub(r"\\\n\s*", " ", text)
instructions = [l.strip() for l in joined.splitlines() if l.strip() and not l.strip().startswith("#")]
install_at = next((i for i, l in enumerate(instructions) if "pip install" in l and "requirements.txt" in l), -1)
install = instructions[install_at] if install_at >= 0 else ""

ok(install_at >= 0, "requirements.txt is installed with pip")
ok("pip uninstall -y setuptools wheel" in install, "the same step removes setuptools and wheel")
ok(re.search(r"python3 -m pip uninstall -y pip(\s|$)", install) is not None, "the same step removes pip itself")
ok("rm -f /usr/local/lib/python3*/ensurepip/_bundled/pip-*.whl" in install, "the pip wheel that ensurepip bundles is deleted")
ok(install.endswith('! python3 -c "import pip" 2>/dev/null'), "the build fails if pip can still be imported")
later = instructions[install_at + 1:] if install_at >= 0 else []
ok(not any(re.search(r"\bpip3?\b|ensurepip|get-pip", l) for l in later), "nothing after the install step uses pip again")
cmd = [l for l in instructions if l.upper().startswith("CMD ")]
ok(len(cmd) == 1 and "pip" not in cmd[0], "the start command does not use pip")
for src in ("server.py", "download_asteroids.py"):
    code = open(src, encoding="utf-8").read()
    found = re.search(r"^\s*(import|from)\s+(pip|setuptools|pkg_resources|ensurepip)\b", code, re.M)
    ok(found is None, f"{src} imports none of pip, setuptools, pkg_resources, ensurepip")

print(f"\n{'FAIL' if failures else 'PASS'}: {failures} failure(s)")
sys.exit(1 if failures else 0)

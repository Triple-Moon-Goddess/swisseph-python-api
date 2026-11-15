"""
The image ships without pip (TRI-14).

Run from the repo root:  .venv/bin/python test_no_pip_in_image.py
Inside the image (SOP 57 §2, Dockerfile.test) it runs from /app.

pip is needed only to install requirements.txt while the image is built; the server and
download_asteroids.py never call it. Leaving it in kept 5 medium and 1 low scanner findings
in the image (Google container scanning, 2026-11-15), the only ones with a published fix.

  1. The Dockerfile removes pip, and the copy ensurepip keeps, in the same step that
     installs requirements.txt, after setuptools and wheel.
  2. Neither server.py nor download_asteroids.py uses pip, ensurepip or a subprocess.
  3. In the image: pip cannot be imported, no pip-*.dist-info is in site-packages, and
     ensurepip has no bundled pip wheel. These read the image itself, so they run where
     the server runs (/app); a run from the repo checks 1 and 2.
"""
import glob
import importlib.util
import os
import re
import sys
import sysconfig

HERE = os.path.dirname(os.path.abspath(__file__))
IN_IMAGE = HERE == '/app' and os.path.exists('/app/ephe')

passes = failures = 0


def check(name, cond, detail=""):
    global passes, failures
    passes, failures = passes + bool(cond), failures + (not cond)
    print(f"  {'✓' if cond else '✗'} {name}{f'  ({detail})' if detail and not cond else ''}")


if not IN_IMAGE:
    print("\n1. the Dockerfile removes pip")
    dockerfile = open(os.path.join(HERE, 'Dockerfile')).read()
    install = re.search(r'RUN pip install --no-cache-dir -r requirements\.txt(?:[^\n]*\\\n)*[^\n]*', dockerfile)
    step = install.group(0) if install else ''
    check("requirements.txt is installed in one RUN step", bool(step))
    check("that step uninstalls setuptools and wheel", 'pip uninstall -y setuptools wheel' in step)
    check("then uninstalls pip itself", 'python -m pip uninstall -y pip' in step
          and step.index('python -m pip uninstall -y pip') > step.index('setuptools wheel'))
    check("and removes ensurepip's bundled wheels", 'ensurepip/_bundled' in step)
    check("no later step runs pip", 'pip ' not in dockerfile[install.end():] if install else False)

print("\n2. the server never calls pip")
for name in ('server.py', 'download_asteroids.py'):
    code = open(os.path.join(HERE, name)).read()
    found = sorted(set(re.findall(r'\b(pip|ensurepip|subprocess)\b', code)))
    check(f"{name} does not use pip, ensurepip or subprocess", not found, ', '.join(found))

if IN_IMAGE:
    print("\n3. the image has no pip")
    site = sysconfig.get_paths()['purelib']
    check("pip cannot be imported", importlib.util.find_spec('pip') is None)
    left = glob.glob(os.path.join(site, 'pip-*.dist-info')) + glob.glob(os.path.join(site, 'pip'))
    check("no pip package or metadata in site-packages", not left, ', '.join(left))
    bundled = glob.glob(os.path.join(sysconfig.get_paths()['stdlib'], 'ensurepip', '_bundled', '*.whl'))
    check("ensurepip has no bundled wheel", not bundled, ', '.join(os.path.basename(b) for b in bundled))
    for tool in ('setuptools', 'wheel'):
        check(f"{tool} is not installed either", importlib.util.find_spec(tool) is None)

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)

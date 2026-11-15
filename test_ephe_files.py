"""
Ephemeris files: every file in ephe/ is real data, never a saved HTML page.

Run from the repo root:  .venv/bin/python test_ephe_files.py

  1. No file anywhere under ephe/ is HTML (the old downloader saved GitHub
     web pages as .se1 files).
  2. Every .se1 file carries the SWISSEPH header naming itself.
  3. pyswisseph reads the files: Chiron, Ceres, Pallas, Juno and Vesta come
     from a Swiss Ephemeris file (not the Moshier fallback), and numbered
     Chiron from ast2/se02060.se1 agrees with body 15 from seas_18.se1.
  4. download_asteroids.py replaces an HTML file, rejects an HTML download,
     leaves a valid file alone, and refuses plain-HTTP URLs.
Fixture date is synthetic (no real person).
"""
import os
import shutil
import sys
import tempfile

import swisseph as swe

import download_asteroids as dl

HERE = os.path.dirname(os.path.abspath(__file__))
EPHE = os.path.join(HERE, 'ephe')
HTML_PAGE = b'\n\n<!DOCTYPE html>\n<html lang="en"><head><title>GitHub</title></head></html>\n'

passes = failures = 0


def check(name, cond, detail=""):
    global passes, failures
    passes, failures = passes + bool(cond), failures + (not cond)
    print(f"  {'✓' if cond else '✗'} {name}{f'  ({detail})' if detail and not cond else ''}")


def looks_like_html(path):
    with open(path, 'rb') as f:
        head = f.read(1024).lower()
    return head.lstrip().startswith(b'<') or b'<!doctype html' in head or b'<html' in head


ephe_files = sorted(os.path.join(root, name) for root, _, names in os.walk(EPHE) for name in names)

print("\n1. no ephe/ file is HTML")
check("ephe/ has files", len(ephe_files) >= 4, f"{len(ephe_files)} files")
for path in ephe_files:
    check(f"{os.path.relpath(path, HERE)} is not HTML", not looks_like_html(path))

print("\n2. every .se1 is Swiss Ephemeris data")
for path in ephe_files:
    if path.endswith('.se1'):
        problem = dl.ephemeris_problem(path)
        check(f"{os.path.relpath(path, HERE)} valid", problem is None, problem)

print("\n3. pyswisseph reads them")
swe.set_ephe_path(EPHE)
jd = swe.julday(1990, 1, 1, 12.0, swe.GREG_CAL)
for name, pid in {"chiron": 15, "ceres": 17, "pallas": 18, "juno": 19, "vesta": 20}.items():
    xx, ret = swe.calc_ut(jd, pid, swe.FLG_SWIEPH | swe.FLG_SPEED)
    check(f"{name} from an ephemeris file", bool(ret & swe.FLG_SWIEPH), f"ret={ret}")
chiron_main = swe.calc_ut(jd, 15, swe.FLG_SWIEPH)[0][0]
try:
    chiron_numbered = swe.calc_ut(jd, swe.AST_OFFSET + 2060, swe.FLG_SWIEPH)[0][0]
    diff = abs((chiron_numbered - chiron_main + 180) % 360 - 180)
    check("numbered Chiron (se02060.se1) matches body 15", diff < 0.01, f"diff {diff:.6f}°")
except swe.Error as e:
    check("numbered Chiron (se02060.se1) readable", False, str(e)[:160])

print("\n4. download_asteroids.py")
real = os.path.join(EPHE, 'ast2', 'se02060.se1')
calls = []


def fake_fetch(body_from=None, body=None):
    def _fetch(url, dest):
        calls.append(url)
        if body_from:
            shutil.copyfile(body_from, dest)
        else:
            with open(dest, 'wb') as f:
                f.write(body)
    return _fetch


with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, 'ast2'))
    target = os.path.join(d, 'ast2', 'se02060.se1')
    with open(target, 'wb') as f:
        f.write(HTML_PAGE)
    check("HTML file is flagged", dl.ephemeris_problem(target) is not None)

    calls.clear()
    ok = dl.ensure_file(d, 'ast2', 'se02060.se1', fake_fetch(body_from=real))
    check("HTML file replaced with real data", ok and dl.ephemeris_problem(target) is None)
    check("download URL is HTTPS", calls and calls[0].startswith('https://'), calls)

    calls.clear()
    ok = dl.ensure_file(d, 'ast2', 'se02060.se1', fake_fetch(body_from=real))
    check("valid file kept, nothing downloaded", ok and not calls, calls)

    os.remove(target)
    ok = dl.ensure_file(d, 'ast2', 'se02060.se1', fake_fetch(body=HTML_PAGE))
    check("HTML download rejected, nothing left behind",
          not ok and os.listdir(os.path.join(d, 'ast2')) == [], os.listdir(os.path.join(d, 'ast2')))

    ok = dl.ensure_file(d, 'ast2', 'se02060.se1', fake_fetch(body=b'SWISSEPH 3\r\nse00001.se1\r\n' + b'\0' * 4096))
    check("download naming another file rejected", not ok)

try:
    dl.fetch('http://www.astro.com/ftp/swisseph/ephe/ast2/se02060.se1', os.devnull)
    check("plain-HTTP URL refused", False, "fetch accepted http://")
except ValueError:
    check("plain-HTTP URL refused", True)
check("source URL is HTTPS", dl.SOURCE.startswith('https://'))

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)

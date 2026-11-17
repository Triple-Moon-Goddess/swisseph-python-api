"""
test_image_script.py — the image is built and pushed on the Mac mini only (SOP 51, SOP 57 §2–§3).

From the repo: runs scripts/image.sh with a stand-in `scutil` that reports a host name, and
DRY_RUN=1 so no Docker or gcloud command runs, and checks that
  1. it refuses on the laptop, on an unknown host, and when the host name cannot be read,
     and an environment variable cannot talk it round;
  2. on the Mini, `build` builds linux/amd64, adds the test layer and runs the tests so that a
     failing test file fails the run;
  3. on the Mini, `push` signs Docker in with the token on stdin, pushes to the project's
     repository and signs Docker out after the push, and refuses an unknown project or tag.
Inside the image (SOP 57 §2, Dockerfile.test) it checks the build script is not shipped.
Run from the repo root:  python test_image_script.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
IN_IMAGE = HERE == '/app' and os.path.exists('/app/ephe')
SCRIPT = os.path.join(HERE, 'scripts', 'image.sh')
MINI = 'Triples-Mac-Mini'
LAPTOP = 'Lisas-MacBook-Air-24gb'

failures = 0


def ok(cond, msg):
    global failures
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    if not cond:
        failures += 1


def run(args, host=None, extra_env=None):
    """Run image.sh with a fake scutil reporting `host` (None: scutil fails)."""
    with tempfile.TemporaryDirectory() as fake:
        scutil = os.path.join(fake, 'scutil')
        with open(scutil, 'w') as f:
            f.write('#!/bin/sh\n' + (f'echo {host}\n' if host else 'exit 1\n'))
        os.chmod(scutil, 0o755)
        env = {'PATH': fake + os.pathsep + '/usr/bin:/bin', 'DRY_RUN': '1', 'HOME': fake}
        env.update(extra_env or {})
        p = subprocess.run(['bash', SCRIPT] + args, env=env, capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr


if IN_IMAGE:
    ok(not os.path.exists('/app/scripts'), 'the build script is not shipped in the image')
else:
    print('host check')
    for host, label in ((LAPTOP, 'the laptop'), ('some-other-host', 'an unknown host'), (None, 'an unreadable host name')):
        for action in (['build', 't1'], ['push', 't1', 'triple-moon-goddess']):
            rc, out, err = run(action, host)
            ok(rc == 2 and 'Mac mini' in err and 'DRY:' not in out,
               f'{action[0]} refuses on {label} and runs nothing (rc {rc})')
    rc, out, err = run(['build', 't1'], LAPTOP, {'HOSTNAME': MINI, 'MINI_HOST': LAPTOP, 'DRY_RUN': '1'})
    ok(rc == 2 and 'DRY:' not in out, 'HOSTNAME / MINI_HOST in the environment do not bypass the check')

    print('build on the Mini')
    rc, out, err = run(['build', 't1'], MINI)
    lines = [l for l in out.splitlines() if l.startswith('DRY:')]
    ok(rc == 0 and len(lines) == 3, f'three commands planned (rc {rc}, {len(lines)} lines) {err.strip()}')
    ok(all('--platform linux/amd64' in l for l in lines), 'every step is linux/amd64, prod\'s platform')
    ok(len(lines) == 3 and 'Dockerfile.test' in lines[1] and 'IMAGE=swisseph:t1' in lines[1], 'the test layer is built on the tested tag')
    ok(len(lines) == 3 and 'exit\\ \\$rc' in lines[2] and 'AUTH_MODE=cloud-run-iam' in lines[2],
       'the in-image run fails when any test file fails')

    print('push on the Mini')
    rc, out, err = run(['push', 't1', 'triple-moon-goddess-dev'], MINI)
    lines = [l for l in out.splitlines() if l.startswith('DRY:')]
    text = '\n'.join(lines)
    dest = 'us-central1-docker.pkg.dev/triple-moon-goddess-dev/cloud-run-source-deploy/swisseph-api:t1'
    ok(rc == 0, f'push plans cleanly (rc {rc}) {err.strip()}')
    ok(any('docker tag swisseph:t1 ' + dest in l for l in lines), 'tags the tested image for the project\'s repository')
    ok('--password-stdin' in text and 'lisahagan@triplemoongoddess.com' in text, 'signs Docker in with a lisahagan@ token on stdin')
    i_push = next((i for i, l in enumerate(lines) if l.startswith('DRY: docker push ')), -1)
    i_out = next((i for i, l in enumerate(lines) if l.startswith('DRY: docker logout ')), -1)
    ok(0 <= i_push < i_out, 'signs Docker out after the push')
    for bad, why in ((['push', 't1', 'someone-elses-project'], 'an unknown project'),
                     (['push', 't1;rm', 'triple-moon-goddess'], 'a tag with shell characters'),
                     (['build', '-t'], 'a tag that looks like a flag'),
                     (['build'], 'a missing tag')):
        rc, out, err = run(bad, MINI)
        ok(rc == 2 and 'DRY:' not in out, f'refuses {why}')

print('FAILED' if failures else 'OK')
sys.exit(1 if failures else 0)

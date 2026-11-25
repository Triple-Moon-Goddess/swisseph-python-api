# Changelog

Changes to the `swisseph-api` image and its build. Older changes are in the pull requests and in TMG SOP 57 §5.

## 2026-11-25

- **A rebuild always installs today's Debian fixes, and the build fails if one is missing.** The prod image scan of 2026-11-25 (app run 45661058275) found a fixable HIGH in the image prod serves: CVE-2026-124851, `libzstd1` 1.5.7+dfsg-1, fixed in 1.5.7+dfsg-1+deb13u1, which Debian published after that image was built. The Dockerfile runs `apt-get upgrade` at build, but Docker reuses that layer from its cache, so a rebuild on the Mac mini kept the old package (seen the same day on the video render image, which is built the same way). `scripts/image.sh build` now builds with `--no-cache --pull`, and a new check runs apt as root in the built image: a package apt would still upgrade, a held-back update, or an apt that fails or gives no answer fails the build before the test layer, naming the package and both versions. No change to `server.py` or to what the image contains beyond current OS packages.
  - **Tests.** `test_image_script.py`: the build command carries `--no-cache --pull`; with a stand-in docker, a stale `libzstd1` fails the build and is named, as do a failing apt, a silent apt and a held-back update, and nothing runs after any of them; an up-to-date image goes on to the tests.

## 2026-11-18

- **No setuid or setgid file in the image (CIS Docker Benchmark v1.6.0, control 4.8; SOP 56 §2).** The Dockerfile clears every setuid and setgid bit (`find / -xdev -perm /6000 -type f -exec chmod a-s {} +`) as the last step that writes files, before the switch to uid 10001. The base `python:3.11-slim` ships 11 such files (`su`, `mount`, `umount`, `passwd`, `chfn`, `chsh`, `gpasswd`, `newgrp`, `chage`, `expiry`, `unix_chkpwd`); the server uses none of them. `scripts/image.sh build` now searches the built image as root and fails the build if any setuid or setgid file is left, before the test layer is built. `test_dockerfile.py` checks the step's place in the Dockerfile and, inside the image, that the server's user sees no such file; `test_image_script.py` checks with a stand-in docker that a file found, or a failed search, stops the build.

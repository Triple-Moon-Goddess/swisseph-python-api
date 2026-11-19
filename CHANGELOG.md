# Changelog

Changes to the `swisseph-api` image and its build. Older changes are in the pull requests and in TMG SOP 57 §5.

## 2026-11-18

- **No setuid or setgid file in the image (CIS Docker Benchmark v1.6.0, control 4.8; SOP 56 §2).** The Dockerfile clears every setuid and setgid bit (`find / -xdev -perm /6000 -type f -exec chmod a-s {} +`) as the last step that writes files, before the switch to uid 10001. The base `python:3.11-slim` ships 11 such files (`su`, `mount`, `umount`, `passwd`, `chfn`, `chsh`, `gpasswd`, `newgrp`, `chage`, `expiry`, `unix_chkpwd`); the server uses none of them. `scripts/image.sh build` now searches the built image as root and fails the build if any setuid or setgid file is left, before the test layer is built. `test_dockerfile.py` checks the step's place in the Dockerfile and, inside the image, that the server's user sees no such file; `test_image_script.py` checks with a stand-in docker that a file found, or a failed search, stops the build.

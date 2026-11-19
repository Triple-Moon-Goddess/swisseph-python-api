#!/usr/bin/env bash
# image.sh — build, test inside the real image, and push the swisseph-api image (SOP 57 §2–§3).
#
# Runs on the Mac mini only. The laptop keeps no cloud sign-in (SOP 51), so the build, the
# in-image tests and the push under the one-hour grant all happen on the Mini; this script
# refuses to run on any other host. The check is a guard against running it by mistake on
# the wrong machine, not an access control: access is the one-hour grant itself.
#
#   scripts/image.sh build <tag>             build linux/amd64, check no setuid/setgid file is
#                                            left (CIS Docker 4.8), add the test layer, run every
#                                            test_*.py in the image (non-zero if any fails)
#   scripts/image.sh push <tag> <project>    tag for Artifact Registry, sign Docker in with a
#                                            lisahagan@ token on stdin, push, print the digest,
#                                            and always sign Docker out again
#
# <project> is triple-moon-goddess-dev or triple-moon-goddess. DRY_RUN=1 prints each command
# instead of running it (the host check still applies).
set -euo pipefail

MINI_HOST="Triples-Mac-Mini"
REGISTRY="us-central1-docker.pkg.dev"
REPOSITORY="cloud-run-source-deploy/swisseph-api"
ACCOUNT="lisahagan@triplemoongoddess.com"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

die() { echo "image.sh: $*" >&2; exit 2; }

run() {
  if [ "${DRY_RUN:-}" = 1 ]; then printf 'DRY:'; printf ' %q' "$@"; printf '\n'; else "$@"; fi
}

require_mini() {
  local host
  host="$(scutil --get LocalHostName 2>/dev/null)" ||
    die "refusing: cannot read this host's name. The chart service image is built and pushed only on the Mac mini (${MINI_HOST}), never on the laptop (SOP 51, SOP 57)."
  [ "$host" = "$MINI_HOST" ] ||
    die "refusing: this host is '${host}'. The chart service image is built and pushed only on the Mac mini (${MINI_HOST}), never on the laptop (SOP 51, SOP 57)."
}

require_tools() {
  [ "${DRY_RUN:-}" = 1 ] && return 0
  command -v docker >/dev/null || die "docker not found (SOP 57 §2: colima + docker + docker-buildx on the Mini)"
  docker buildx version >/dev/null 2>&1 || die "docker buildx not found (Homebrew docker-buildx plugin)"
}

valid_tag() {
  [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] || die "bad tag '$1' (letters, digits, . _ - ; at most 64)"
}

valid_project() {
  case "$1" in
    triple-moon-goddess|triple-moon-goddess-dev) ;;
    *) die "unknown project '$1' (triple-moon-goddess-dev or triple-moon-goddess)" ;;
  esac
}

# CIS Docker Benchmark 4.8: no file in the image may keep a setuid or setgid bit. find runs as
# root, so it reads every folder (the tests run as uid 10001 and cannot); any path it prints, or
# a find that fails, fails the build.
setuid_check() {
  local img="$1" found
  if [ "${DRY_RUN:-}" = 1 ]; then
    run docker run --rm --platform linux/amd64 --user 0 --entrypoint find "$img" / -xdev -perm /6000 -type f
    return 0
  fi
  found="$(docker run --rm --platform linux/amd64 --user 0 --entrypoint find "$img" / -xdev -perm /6000 -type f)" ||
    die "the setuid/setgid check could not run on ${img}"
  [ -z "$found" ] || die "setuid/setgid files left in ${img} (CIS Docker 4.8): $(printf '%s' "$found" | tr '\n' ' ')"
  echo "setuid/setgid files in ${img}: 0"
}

cmd_build() {
  local tag="$1"
  run docker buildx build --platform linux/amd64 --load -t "swisseph:${tag}" "$REPO_ROOT"
  setuid_check "swisseph:${tag}"
  run docker buildx build --platform linux/amd64 --load --build-arg "IMAGE=swisseph:${tag}" \
    -f "$REPO_ROOT/Dockerfile.test" -t "swisseph:${tag}-test" "$REPO_ROOT"
  # Every test file must exit 0; a failure makes the whole run fail.
  run docker run --rm --platform linux/amd64 -e AUTH_MODE=cloud-run-iam --entrypoint sh \
    "swisseph:${tag}-test" -c 'rc=0; for t in test_*.py; do python "$t" || { echo "FAILED $t"; rc=1; }; done; exit $rc'
}

docker_login() {
  if [ "${DRY_RUN:-}" = 1 ]; then
    echo "DRY: gcloud auth print-access-token --account ${ACCOUNT} | docker login -u oauth2accesstoken --password-stdin https://${REGISTRY}"
  else
    gcloud auth print-access-token --account "$ACCOUNT" |
      docker login -u oauth2accesstoken --password-stdin "https://${REGISTRY}" >/dev/null
  fi
}

docker_logout() {
  if [ "${DRY_RUN:-}" = 1 ]; then run docker logout "https://${REGISTRY}"
  else docker logout "https://${REGISTRY}" >/dev/null 2>&1 || true; fi
}

cmd_push() {
  local tag="$1" project="$2" dest
  dest="${REGISTRY}/${project}/${REPOSITORY}:${tag}"
  run docker tag "swisseph:${tag}" "$dest"
  trap docker_logout EXIT
  docker_login
  run docker push "$dest"
  if [ "${DRY_RUN:-}" = 1 ]; then
    echo "DRY: digest of ${dest}"
  else
    echo "pushed: $(docker image inspect --format '{{join .RepoDigests "\n"}}' "$dest" | grep "^${REGISTRY}/${project}/")"
  fi
  # Docker is signed out by the EXIT trap, also after a failed push.
}

main() {
  require_mini
  local action="${1:-}"
  case "$action" in
    build)
      [ $# -eq 2 ] || die "usage: scripts/image.sh build <tag>"
      valid_tag "$2"; require_tools; cmd_build "$2" ;;
    push)
      [ $# -eq 3 ] || die "usage: scripts/image.sh push <tag> <project>"
      valid_tag "$2"; valid_project "$3"; require_tools; cmd_push "$2" "$3" ;;
    *) die "usage: scripts/image.sh build <tag> | push <tag> <project>" ;;
  esac
}

main "$@"

#!/usr/bin/env bash

set -Eeuo pipefail

fail() {
  printf 'Hermetic runner preflight failed: %s\n' "$*" >&2
  exit 2
}

usage() {
  printf 'Usage: %s --preflight\n' "$0"
}

if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "$#" -ne 1 || "$1" != "--preflight" ]]; then
  usage >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
test_repo_root="$(cd "$script_dir/.." && pwd)"
sut_repo_root="$(cd "$test_repo_root/../totally-testable-banking" && pwd)"
compose_file="${SUT_COMPOSE_FILE:-$sut_repo_root/compose.yaml}"

[[ -f "$compose_file" ]] || fail "SUT Compose file does not exist: $compose_file"
compose_file="$(cd "$(dirname "$compose_file")" && pwd)/$(basename "$compose_file")"

case "$compose_file" in
  "$sut_repo_root"/*) ;;
  *) fail "SUT Compose file must be inside $sut_repo_root" ;;
esac

[[ -x "$test_repo_root/.venv/bin/pytest" ]] ||
  fail "pytest is unavailable; run 'uv sync' in $test_repo_root"
command -v docker >/dev/null 2>&1 || fail "Docker CLI is unavailable"
docker compose version >/dev/null 2>&1 || fail "Docker Compose is unavailable"
docker info >/dev/null 2>&1 || fail "Docker daemon is unavailable"

run_suffix="$(date -u +%Y%m%d%H%M%S)-$$"
compose_project="ttb-api-tests-$run_suffix"
artifact_dir="$test_repo_root/artifacts/hermetic/$compose_project"

export COMPOSE_PROJECT_NAME="$compose_project"
export BANK_API_HOST_PORT=0
export PROCESSOR_HOST_PORT=0
export PROCESSOR_CONTROL_SECRET="hermetic-$compose_project"

docker compose --file "$compose_file" config --quiet ||
  fail "SUT Compose configuration is invalid"

printf 'Hermetic runner preflight passed\n'
printf '  compose project: %s\n' "$compose_project"
printf '  compose file: %s\n' "$compose_file"
printf '  API host port: dynamic\n'
printf '  processor host port: dynamic\n'
printf '  artifact directory: %s\n' "$artifact_dir"

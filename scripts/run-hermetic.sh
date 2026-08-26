#!/usr/bin/env bash

set -Eeuo pipefail

fail() {
  printf 'Hermetic runner failed: %s\n' "$*" >&2
  exit 2
}

usage() {
  printf 'Usage: %s {--preflight|--infrastructure-check}\n' "$0"
}

if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "$#" -ne 1 ]]; then
  usage >&2
  exit 2
fi

mode="$1"
case "$mode" in
  --preflight | --infrastructure-check) ;;
  *)
    usage >&2
    exit 2
    ;;
esac

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
export BANK_API_IMAGE="ttb-api-tests-api-$run_suffix"

compose() {
  docker compose --project-name "$compose_project" --file "$compose_file" "$@"
}

compose config --quiet || fail "SUT Compose configuration is invalid"

printf 'Hermetic runner preflight passed\n'
printf '  compose project: %s\n' "$compose_project"
printf '  compose file: %s\n' "$compose_file"
printf '  API host port: dynamic\n'
printf '  processor host port: dynamic\n'
printf '  artifact directory: %s\n' "$artifact_dir"

if [[ "$mode" == "--preflight" ]]; then
  exit 0
fi

cleanup_enabled=false
cleanup() {
  exit_status="$?"
  cleanup_status=0
  trap - EXIT INT TERM

  if [[ "$cleanup_enabled" == true ]]; then
    printf 'Removing hermetic Compose resources for %s\n' "$compose_project"
    compose down --volumes --remove-orphans || cleanup_status="$?"
    docker image rm "$BANK_API_IMAGE" >/dev/null 2>&1 || true
    docker image rm "$compose_project-mock-processor" >/dev/null 2>&1 || true
  fi

  if [[ "$exit_status" -eq 0 && "$cleanup_status" -ne 0 ]]; then
    exit_status="$cleanup_status"
  fi

  exit "$exit_status"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
cleanup_enabled=true

printf 'Building isolated migration images\n'
compose build api mock-processor

printf 'Starting fresh database services\n'
compose up --detach --wait postgres processor-postgres

printf 'Applying banking API migrations\n'
compose run --rm --no-deps api alembic upgrade head

printf 'Applying processor migrations\n'
compose run --rm --no-deps mock-processor alembic upgrade head

printf 'Hermetic infrastructure check passed\n'

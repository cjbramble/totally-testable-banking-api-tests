#!/usr/bin/env bash

set -Eeuo pipefail

fail() {
  printf 'Hermetic runner failed: %s\n' "$*" >&2
  exit 2
}

usage() {
  printf 'Usage: %s {--preflight|--infrastructure-check|--application-check|--test-serial|--test-parallel|--test-concurrency|--test}\n' "$0"
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
  --preflight | --infrastructure-check | --application-check | --test-serial | --test-parallel | --test-concurrency | --test) ;;
  *)
    usage >&2
    exit 2
    ;;
esac

test_mode=false
case "$mode" in
  --test | --test-*) test_mode=true ;;
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
docker buildx version >/dev/null 2>&1 || fail "Docker Buildx is unavailable"
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

mkdir -p "$artifact_dir"
current_phase="runner initialization"
cleanup_enabled=false

run_logged() {
  local log_name="$1"
  shift
  "$@" 2>&1 | tee "$artifact_dir/$log_name"
}

run_static_quality_checks() {
  cd "$test_repo_root"
  .venv/bin/ruff check .
  .venv/bin/ruff format --check .
  .venv/bin/mypy
}

redact_artifact_secrets() {
  "$test_repo_root/.venv/bin/python" - "$artifact_dir" "$PROCESSOR_CONTROL_SECRET" <<'PY'
from pathlib import Path
import sys

artifact_dir = Path(sys.argv[1])
secret = sys.argv[2]

for path in artifact_dir.rglob("*"):
    if not path.is_file():
        continue
    try:
        content = path.read_text()
    except UnicodeDecodeError:
        continue
    if secret in content:
        path.write_text(content.replace(secret, "[REDACTED]"))
PY
}

cleanup() {
  exit_status="$?"
  cleanup_status=0
  trap - EXIT INT TERM

  if [[ "$exit_status" -ne 0 ]]; then
    {
      printf 'mode=%s\n' "$mode"
      printf 'phase=%s\n' "$current_phase"
      printf 'exit_status=%s\n' "$exit_status"
      printf 'compose_project=%s\n' "$compose_project"
    } >"$artifact_dir/failure-summary.txt"

    if [[ "$cleanup_enabled" == true ]]; then
      printf 'Capturing Compose diagnostics in %s\n' "$artifact_dir"
      compose ps --all >"$artifact_dir/compose-ps.txt" 2>&1 || true
      compose logs --no-color >"$artifact_dir/compose.log" 2>&1 || true
    fi
  fi

  if [[ "$cleanup_enabled" == true ]]; then
    printf 'Removing hermetic Compose resources for %s\n' "$compose_project"
    compose down --volumes --remove-orphans || cleanup_status="$?"
    docker image rm "$BANK_API_IMAGE" >/dev/null 2>&1 || true
    docker image rm "$compose_project-mock-processor" >/dev/null 2>&1 || true
    docker image rm "$compose_project-processor-callback-worker" >/dev/null 2>&1 || true
  fi

  redact_artifact_secrets || true

  if [[ "$exit_status" -eq 0 && "$cleanup_status" -ne 0 ]]; then
    exit_status="$cleanup_status"
  fi

  exit "$exit_status"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ "$test_mode" == true ]]; then
  [[ -x "$test_repo_root/.venv/bin/ruff" ]] || fail "Ruff is unavailable; run 'uv sync'"
  [[ -x "$test_repo_root/.venv/bin/mypy" ]] || fail "mypy is unavailable; run 'uv sync'"

  printf 'Running static quality checks\n'
  current_phase="static quality checks"
  run_logged "static-quality.log" run_static_quality_checks
fi

printf 'Building isolated migration images\n'
current_phase="migration image build"
cleanup_enabled=true
run_logged "migration-image-build.log" compose build api mock-processor

if [[ "$mode" == "--application-check" || "$test_mode" == true ]]; then
  printf 'Building isolated callback worker image\n'
  current_phase="callback worker image build"
  run_logged "callback-worker-image-build.log" compose build processor-callback-worker
fi

printf 'Starting fresh database services\n'
current_phase="database startup"
run_logged "database-startup.log" compose up --detach --wait postgres processor-postgres

printf 'Applying banking API migrations\n'
current_phase="banking API migrations"
run_logged "banking-api-migrations.log" compose run --rm --no-deps api alembic upgrade head

printf 'Applying processor migrations\n'
current_phase="processor migrations"
run_logged "processor-migrations.log" compose run --rm --no-deps mock-processor alembic upgrade head

printf 'Hermetic infrastructure check passed\n'

if [[ "$mode" == "--infrastructure-check" ]]; then
  exit 0
fi

probe_url() {
  "$test_repo_root/.venv/bin/python" -c \
    'import sys, urllib.request; response = urllib.request.urlopen(sys.argv[1], timeout=2); status = response.status; response.close(); raise SystemExit(0 if status == 200 else 1)' \
    "$1" >/dev/null 2>&1
}

wait_for_url() {
  local label="$1"
  local url="$2"
  local deadline=$((SECONDS + 60))

  until probe_url "$url"; do
    if ((SECONDS >= deadline)); then
      fail "$label did not become ready within 60 seconds: $url"
    fi
    sleep 1
  done
}

printf 'Starting isolated application services\n'
current_phase="application startup"
run_logged "application-startup.log" compose up --detach --wait --wait-timeout 60 \
  api \
  mock-processor \
  worker \
  scheduled-transfer-worker \
  processor-callback-worker

api_binding="$(compose port api 8000)"
processor_binding="$(compose port mock-processor 8001)"
api_port="${api_binding##*:}"
processor_port="${processor_binding##*:}"

[[ "$api_port" =~ ^[0-9]+$ ]] || fail "Could not discover the banking API host port"
[[ "$processor_port" =~ ^[0-9]+$ ]] || fail "Could not discover the processor host port"

export SUT_BASE_URL="http://127.0.0.1:$api_port"
export PROCESSOR_CONTROL_URL="http://127.0.0.1:$processor_port"

current_phase="application readiness"
wait_for_url "banking API" "$SUT_BASE_URL/health/ready"
wait_for_url "processor" "$PROCESSOR_CONTROL_URL/health/ready"

printf 'Hermetic application check passed\n'
printf '  banking API: %s\n' "$SUT_BASE_URL"
printf '  processor: %s\n' "$PROCESSOR_CONTROL_URL"

if [[ "$mode" == "--application-check" ]]; then
  exit 0
fi

export SUT_COMPOSE_FILE="$compose_file"

run_pytest() {
  local label="$1"
  local report_name="$2"
  shift 2

  printf 'Running %s\n' "$label"
  current_phase="$label"
  (
    cd "$test_repo_root"
    .venv/bin/pytest \
      "$@" \
      --junitxml="$artifact_dir/$report_name" \
      -o "junit_suite_name=$label-$compose_project"
  ) 2>&1 | tee "$artifact_dir/${report_name%.xml}.log"
}

case "$mode" in
  --test-serial)
    run_pytest "complete serial suite" "serial.xml"
    ;;
  --test-parallel)
    run_pytest "ordinary two-worker suite" "parallel.xml" -n 2 -m "not concurrency"
    ;;
  --test-concurrency)
    run_pytest "dedicated concurrency suite" "concurrency.xml" -m concurrency
    ;;
  --test)
    run_pytest "smoke selection" "smoke.xml" -m smoke
    run_pytest "complete serial suite" "serial.xml"
    run_pytest "ordinary two-worker suite" "parallel.xml" -n 2 -m "not concurrency"
    run_pytest "dedicated concurrency suite" "concurrency.xml" -m concurrency
    ;;
esac

printf 'Hermetic test mode passed: %s\n' "$mode"
printf '  JUnit directory: %s\n' "$artifact_dir"

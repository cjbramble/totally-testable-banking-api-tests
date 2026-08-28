# Totally Testable Banking API Tests

Independent black-box API automation for the local Totally Testable Banking API.

## Prerequisites

The repository expects:

- [uv](https://docs.astral.sh/uv/) with access to Python 3.13;
- the sibling `totally-testable-banking` repository at
  `../totally-testable-banking`;
- Docker Engine or Docker Desktop with the Docker CLI, Compose, and Buildx available on `PATH`
  for live worker-control and hermetic runs.

Verify the external tools from the API-test repository root:

```bash
uv --version
docker info
docker compose version
docker buildx version
test -f ../totally-testable-banking/compose.yaml
```

Docker is unnecessary for static checks and automation-unit tests. Live local tests require the
sibling application stack. Hermetic modes create their own isolated stack and must not target a
remote service.

## Setup

Create the locked project environment and install the Git hook:

```bash
uv sync --frozen
uv run --frozen pre-commit install
```

No virtual-environment activation is required. Project tools are invoked through
`uv run --frozen`, which resolves them from the project environment without changing
`uv.lock`.

Create the live-local configuration once:

```bash
test -f .env || cp .env.example .env
```

Set `PROCESSOR_CONTROL_SECRET` in `.env` to the local simulated processor's configured
credential. The remaining defaults target the sibling stack:

- banking API: `http://127.0.0.1:8009`;
- processor control API: `http://127.0.0.1:8011`;
- Compose file: `../totally-testable-banking/compose.yaml`;
- request timeout: 10 seconds.

## Verification workflows

### Static checks and automation-unit tests

These commands do not require the banking application:

```bash
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy
uv run --frozen pytest -q -m unit
uv run --frozen pre-commit run --all-files
```

Pre-commit invokes Ruff and mypy through `uv run --frozen`, so committing does not depend on an
activated virtual environment or direct `ruff` and `mypy` executables on the caller's `PATH`.

### Live local serial tests

Start the sibling stack and run the serial diagnostic baseline:

```bash
make -C ../totally-testable-banking up
uv run --frozen pytest -q
```

Useful focused selections include:

```bash
uv run --frozen pytest -q tests/auth
uv run --frozen pytest -q -m smoke
uv run --frozen pytest -q -m contract
```

Live tests register unique users and use only local published interfaces. They require the
`.env` values to match the running sibling stack.

### Live local xdist and controlled concurrency

After the serial suite passes, verify ordinary test isolation with two worker processes, then run
the deliberately synchronized race tests separately:

```bash
uv run --frozen pytest -q -n 2 -m "not concurrency"
uv run --frozen pytest -q -m concurrency
```

xdist overlaps independent tests across worker processes. The `concurrency` selection instead
coordinates simultaneous requests inside each test, so it remains a separate serial selection.

### Fresh hermetic execution

The hermetic runner validates Docker CLI, Compose, Buildx, the daemon, required project-environment
executables, and the sibling Compose path. Preflight is read-only and does not create Docker
resources:

```bash
./scripts/run-hermetic.sh --preflight
```

The remaining modes build uniquely named images and use fresh databases, dynamic host ports, and
guaranteed teardown:

```bash
./scripts/run-hermetic.sh --infrastructure-check
./scripts/run-hermetic.sh --application-check
./scripts/run-hermetic.sh --test-serial
./scripts/run-hermetic.sh --test-parallel
./scripts/run-hermetic.sh --test-concurrency
./scripts/run-hermetic.sh --test
```

- `--infrastructure-check` builds migration images and applies both fresh schemas.
- `--application-check` also starts the API, processor, and workers and verifies readiness.
- Focused test modes run static checks plus one requested execution strategy.
- `--test` runs static checks, smoke, complete serial, ordinary two-worker, and dedicated
  concurrency phases.

Every non-preflight mode creates `artifacts/hermetic/<run-id>/` before its first build or static
step. Major phases write separate logs; pytest phases also write JUnit XML. A failed run records
the mode, failing phase, exit status, Compose status, and Compose logs when Docker startup has
begun. Generated processor-control credentials are redacted from text artifacts before exit.
Docker resources are removed whether the run passes or fails.

Official references: [uv project execution](https://docs.astral.sh/uv/concepts/projects/run/),
[uv lock and sync behavior](https://docs.astral.sh/uv/concepts/projects/sync/),
[pre-commit usage](https://pre-commit.com/#usage), and
[Docker Compose installation](https://docs.docker.com/compose/install/).

### Verified final gate

On 2026-08-28, `./scripts/run-hermetic.sh --test` passed against a fresh, isolated stack:

| Phase | Result |
| --- | --- |
| Ruff, format, and mypy | Passed |
| Fresh database migrations and application readiness | Passed |
| Smoke selection | 3 passed |
| Complete serial suite | 133 passed |
| Ordinary suite with two xdist workers | 130 passed |
| Dedicated concurrency suite | 3 passed |
| Compose teardown | No run containers, network, or volumes remained |

Run `ttb-api-tests-20260828062625-7063` produced logs for static checks, builds, migrations,
application startup, and each pytest phase plus separately named `smoke.xml`, `serial.xml`,
`parallel.xml`, and `concurrency.xml` reports. Each JUnit suite name includes both its execution
phase and the unique run ID. Genuine failed run `ttb-api-tests-20260827040309-79386` identified the
failed test and its `6.00` versus `25.00` assertion, captured Compose status and logs, and left no
run containers, network, or volumes. No failure was manufactured solely for gate evidence.

Directories group tests by owned behavior:

- `activity/` — activity projections and keyset pagination;
- `auth/` — registration, authentication, browser sessions, and authorization;
- `deposits/` and `withdrawals/` — asynchronous lifecycle and idempotency behavior;
- `processor/` — the banking-service and simulated-processor boundary;
- `smoke/` — essential live-service readiness;
- `transfers/` — P2P, own-account, idempotency, rejection, and concurrency behavior;
- `unit/` — isolated tests of this automation package.

Directories answer where behavior is owned. Markers select cross-cutting purpose or risk.
For example, `contract` is reserved for the bank–processor boundary, while `invariant` and
`negative` span several product areas. Controlled races use `concurrency`; ordinary parallel
suite execution is a separate isolation concern.

Within a capability directory, files group coherent behavior families. For example, activity
entry projection, pagination traversal, and pagination validation are separate modules; transfer
modules distinguish immediate movement, scheduled lifecycle, rejected requests, concurrency, and
idempotency scope. File boundaries follow behavior and review ownership rather than a line quota.

## Test boundary

This repository tests the banking API through its published HTTP interfaces.
It does not:

- import SUT implementation code;
- access the SUT database directly;
- use canonical demo users;
- reset shared state globally;
- target non-local services;
- store credentials in the repository.

Live tests register unique users through normal product routes. Registration creates empty
checking and savings accounts; tests do not depend on the shared demo users.

## Risk coverage map

This map assigns each important risk to one primary owning layer. Secondary observables strengthen
the result without replacing the primary oracle.

| Risk | Owning layer | Test module | Setup strategy | Primary oracle | Secondary oracle | Parallel-safety notes | Why another layer does not own it |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Unsafe or incomplete local configuration | Automation unit | `tests/unit/test_settings.py` | Isolated environment changes with `monkeypatch` | Settings validation result | Specific validation message | No shared process state persists after each test | A live API test should not be needed to prove test-runner safeguards |
| Registration, token authentication, and browser sessions | Banking API | `tests/auth/` | Unique users created through product routes | Documented status and response model | Account list, cookie persistence, CSRF rejection, or error envelope | UUID-based users; function-scoped clients | UI coverage cannot efficiently enumerate the HTTP authentication contract |
| Resource ownership and authorization | Banking API | `tests/auth/test_authorization.py` and resource modules | Separate owner and outsider users | Owner succeeds while outsider is rejected | No protected resource data is exposed | Every test owns its users and resources | Unit tests cannot prove enforcement across the deployed HTTP boundary |
| P2P and own-account money movement | Banking API | `tests/transfers/test_transfers.py`, `tests/transfers/test_account_transfers.py`, and `tests/transfers/test_scheduled_account_transfers.py` | Generated users plus settled deposits | Exact debit and credit amounts | Operation status and activity records | Per-test accounts and idempotency keys | UI assertions are slower and less precise for balance invariants |
| Invalid transfer requests have no financial effect | Banking API | `tests/transfers/test_transfer_request_validation.py`, `tests/transfers/test_transfer_account_rejections.py`, and `tests/transfers/test_account_transfer_rejections.py` | Funded source plus isolated invalid request | Documented rejection | Before-and-after balances remain equal | Unique users, accounts, and request keys | Schema-only tests cannot prove the absence of a financial side effect |
| Retry and idempotency safety | Banking API | Deposit, withdrawal, and transfer idempotency modules | Unique operation-scoped idempotency keys | One operation identity and one financial effect | Cross-user and cross-operation key independence | Keys include UUIDs and state is test-owned | Client unit tests cannot prove server-side deduplication |
| Asynchronous deposit and withdrawal lifecycle | Banking API | `tests/deposits/test_deposits.py`, `tests/withdrawals/test_withdrawals.py` | Product request followed by bounded status polling | Terminal operation status and exact balance change | Matching activity entry | Polling is operation-specific; no fixed sleeps | Processor-only tests cannot prove the banking API projection and ledger effect |
| Bank-to-processor interaction contract | Bank-processor boundary | `tests/processor/test_processor_contract.py` | Operation-scoped processor scenario through its control API | Banking operation reflects the configured processor outcome | Balance, activity, reservation, and duplicate-callback invariants | Unique scenario and instruction identifiers | Ordinary banking API tests should not couple to simulated-provider controls |
| Activity ordering, pagination, and isolation | Banking API | `tests/activity/` | Multiple generated operations with captured cursors | Stable, complete, correctly ordered traversal | Cursor tamper and cross-user isolation checks | Activity belongs only to generated users | Database checks would bypass the published projection and cursor behavior |
| Scheduled transfer execution and cancellation | Banking API plus bounded local worker control | `tests/transfers/test_scheduled_account_transfers.py` | Future-dated operation and exact-operation worker invocation | Correct pre-due, canceled, posted, or failed state | Exact balances and activity | Worker command targets one operation and date; no global clock/reset | Waiting on wall time is nondeterministic, while direct database mutation breaks the boundary |
| Concurrent transfer invariants | Banking API | `tests/transfers/test_transfer_concurrency.py` | Coordinated requests against test-owned accounts | No overspend or duplicate financial effect | Coherent terminal operations and balances | Runs as a dedicated serial pytest selection because each test creates its own request concurrency | Serial functional tests cannot expose race conditions; generic xdist overlap is not a controlled race |
| Automation client, models, polling, and command wrappers | Automation unit | `tests/unit/` | HTTPX transports and local stubs | Exact request serialization, parsing, and control flow | Diagnostic exceptions and strict model validation | No live shared services | These are implementation details of the test harness, not banking product behavior |

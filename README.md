# Totally Testable Banking API Tests

Independent black-box API automation for the local Totally Testable Banking API.

## Setup

Requirements:

- Python 3.13
- uv
- a local Totally Testable Banking API

Create the environment:

```bash
uv sync
pre-commit install
```

Create local configuration from the example:

```bash
cp .env.example .env
```

The SUT must be running locally. From the sibling `totally-testable-banking`
repository:

```bash
make up
```

The default API address is `http://127.0.0.1:8009`.
`SUT_COMPOSE_FILE` identifies the local SUT Compose file used for bounded worker actions and
defaults to the sibling `totally-testable-banking/compose.yaml`.
The processor-control address defaults to `http://127.0.0.1:8011`.
`PROCESSOR_CONTROL_SECRET` must match the credential configured for the local
simulated processor. It is required at runtime and must not contain a hosted
or production credential.

## Verification

Run the focused or complete test suite:

```bash
pytest -q
pytest -q tests/auth
pytest -q -m smoke
pytest -q -m unit
pytest -q -m contract
pytest -q -m concurrency
pytest -q -n 2 -m "not concurrency"
```

The default complete run remains serial. The `-n 2` command starts two xdist worker processes
and checks that ordinary tests remain isolated when their execution order overlaps. Deliberate
concurrency tests run separately because they already synchronize multiple requests within one
test.

Validate hermetic-runner prerequisites without changing Docker state:

```bash
./scripts/run-hermetic.sh --preflight
```

Build fresh migration images, apply both database schemas, and verify isolated teardown:

```bash
./scripts/run-hermetic.sh --infrastructure-check
```

Start the isolated API application stack and verify its readiness through dynamically assigned
host ports:

```bash
./scripts/run-hermetic.sh --application-check
```

The application check starts the banking API, processor, and their background workers only after
both fresh databases are migrated. It verifies the banking API and processor readiness endpoints
from the host, then removes the generated containers, network, volumes, and images.

Run the complete hermetic verification gate:

```bash
./scripts/run-hermetic.sh --test
```

Use a focused hermetic test mode when only one execution strategy needs verification:

```bash
./scripts/run-hermetic.sh --test-serial
./scripts/run-hermetic.sh --test-parallel
./scripts/run-hermetic.sh --test-concurrency
```

The focused modes run the complete suite serially, ordinary tests with two xdist workers, or the
deliberate concurrency tests serially, respectively. The comprehensive `--test` mode runs all
three strategies plus the smoke selection.

Every test mode runs Ruff, formatting, and mypy; creates an isolated application stack; and writes
JUnit XML beneath `artifacts/hermetic/`. The generated Docker resources are removed whether pytest
passes or fails.

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

Run `ttb-api-tests-20260828035126-89323` produced separately named `smoke.xml`, `serial.xml`,
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

Run the static quality checks:

```bash
ruff check .
ruff format --check .
mypy
pre-commit run --all-files
```

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
| P2P and own-account money movement | Banking API | `tests/transfers/test_transfers.py`, `tests/transfers/test_account_transfers.py` | Generated users plus settled deposits | Exact debit and credit amounts | Operation status and activity records | Per-test accounts and idempotency keys | UI assertions are slower and less precise for balance invariants |
| Invalid transfer requests have no financial effect | Banking API | `tests/transfers/test_transfer_rejections.py` | Funded source plus isolated invalid request | Documented rejection | Before-and-after balances remain equal | Unique users, accounts, and request keys | Schema-only tests cannot prove the absence of a financial side effect |
| Retry and idempotency safety | Banking API | Deposit, withdrawal, and transfer idempotency modules | Unique operation-scoped idempotency keys | One operation identity and one financial effect | Cross-user and cross-operation key independence | Keys include UUIDs and state is test-owned | Client unit tests cannot prove server-side deduplication |
| Asynchronous deposit and withdrawal lifecycle | Banking API | `tests/deposits/test_deposits.py`, `tests/withdrawals/test_withdrawals.py` | Product request followed by bounded status polling | Terminal operation status and exact balance change | Matching activity entry | Polling is operation-specific; no fixed sleeps | Processor-only tests cannot prove the banking API projection and ledger effect |
| Bank-to-processor interaction contract | Bank-processor boundary | `tests/processor/test_processor_contract.py` | Operation-scoped processor scenario through its control API | Banking operation reflects the configured processor outcome | Balance, activity, reservation, and duplicate-callback invariants | Unique scenario and instruction identifiers | Ordinary banking API tests should not couple to simulated-provider controls |
| Activity ordering, pagination, and isolation | Banking API | `tests/activity/test_activity.py` | Multiple generated operations with captured cursors | Stable, complete, correctly ordered traversal | Cursor tamper and cross-user isolation checks | Activity belongs only to generated users | Database checks would bypass the published projection and cursor behavior |
| Scheduled transfer execution and cancellation | Banking API plus bounded local worker control | `tests/transfers/test_account_transfers.py` | Future-dated operation and exact-operation worker invocation | Correct pre-due, canceled, posted, or failed state | Exact balances and activity | Worker command targets one operation and date; no global clock/reset | Waiting on wall time is nondeterministic, while direct database mutation breaks the boundary |
| Concurrent transfer invariants | Banking API | `tests/transfers/test_transfer_concurrency.py` | Coordinated requests against test-owned accounts | No overspend or duplicate financial effect | Coherent terminal operations and balances | Runs as a dedicated serial pytest selection because each test creates its own request concurrency | Serial functional tests cannot expose race conditions; generic xdist overlap is not a controlled race |
| Automation client, models, polling, and command wrappers | Automation unit | `tests/unit/` | HTTPX transports and local stubs | Exact request serialization, parsing, and control flow | Diagnostic exceptions and strict model validation | No live shared services | These are implementation details of the test harness, not banking product behavior |

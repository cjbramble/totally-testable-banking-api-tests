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
```

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

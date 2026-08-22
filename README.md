# Totally Testable Banking API Tests

Independent black-box API automation for the local Totally Testable Banking API.

## Setup

Requirements:

- Python 3.13
- uv
- a local Totally Testable Banking API
- local test-support credentials

Create the environment:

```bash
uv sync
pre-commit install
```

Create local configuration from the example:

```bash
cp .env.example .env
```

Set `TEST_SUPPORT_TOKEN` in `.env` to the same local test-support token used by
the running SUT. Never commit `.env` or real credentials.

The SUT must be running locally with test support enabled. From the sibling
`totally-testable-banking` repository, for example:

```bash
TEST_SUPPORT_ENABLED=true \
TEST_SUPPORT_TOKEN=local-only-token \
make up
```

The default API address is `http://127.0.0.1:8009`.

## Verification

Run the focused or complete test suite:

```bash
pytest -q
```

Run the static quality checks:

```bash
ruff check .
ruff format --check .
mypy
pre-commit run --all-files
```

## Test boundary

This repository tests the banking API through its published HTTP contracts.
It does not:

- import SUT implementation code;
- access the SUT database directly;
- use canonical demo users;
- reset shared state globally;
- target non-local services;
- store credentials in the repository.

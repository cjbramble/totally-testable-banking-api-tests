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

Live tests register unique users through normal product routes. Registration creates empty
checking and savings accounts; tests do not depend on the shared demo users.

---
name: run-tests
description: Run test suites, manage VCR.py HTTP cassettes, and execute Ruff linter and formatter.
---

# Testing & Quality Assurance Workflows

This skill guides running the test suite, recording/updating VCR.py network cassettes, and executing code formatting and linting for `ytg-music`.

---

## 1. Running Unit Tests

Run tests using `uv`:

```bash
# Run all tests
uv run pytest

# Run with verbose output and test names
uv run pytest -v

# Run a specific test module
uv run pytest tests/test_services.py

# Run a specific test function
uv run pytest tests/test_services.py -k "test_best_thumbnail_selection"
```

### Headless Environments (CI / Virtual Display)
If running on a headless Linux machine or container without a Wayland/X11 display server:

```bash
xvfb-run -a uv run pytest
```

---

## 2. Managing VCR.py Network Cassettes

Tests that interact with YouTube Music APIs use `pytest-recording` (VCR.py) and have the `@pytest.mark.vcr()` decorator. Recorded HTTP interactions are saved under `tests/cassettes/`.

### Re-recording / Updating Cassettes
When `ytmusicapi` changes or new API endpoints/features are introduced:

```bash
# Re-record cassettes for all VCR tests
uv run pytest --record-mode=rewrite

# Re-record a specific test's cassette
uv run pytest --record-mode=rewrite tests/test_services.py -k "test_api_get_home"
```

### Test Isolation Safeguards in `conftest.py`
- All tests run in anonymous mode (`force_anonymous_mode` fixture prevents loading local user cookies).
- `run_in_background` is mocked to execute synchronously to prevent threading races.
- Authorization cookies and tokens are automatically scrubbed from cassettes (`DUMMY_AUTHORIZATION`, `DUMMY_COOKIE`).

---

## 3. Code Linting and Formatting (Ruff)

The project enforces PEP 8, import sorting (`isort`), and Pyflakes rules via `ruff`.

```bash
# Check code for linting issues
uv run ruff check .

# Automatically apply safe lint fixes
uv run ruff check --fix .

# Check code formatting without modifying files
uv run ruff format --check .

# Format all code in place
uv run ruff format .
```

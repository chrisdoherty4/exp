# CLAUDE.md

## Build & run

```bash
make install       # install in editable mode
make install-test  # install with test deps
make test          # run tests
make test-v        # run tests (verbose)
make run           # continuous monitoring
make run-once      # single check
```

The venv lives at `.venv/`. All make targets handle venv creation automatically.

## Project layout

- `stock_checker/` — main package
  - `checkers/base.py` — `StockStatus` enum (`IN_STOCK`, `OUT_OF_STOCK`, `UNKNOWN`, `ERROR`) and `Checker` protocol
  - `checkers/target.py` — `TargetChecker`: async Redsky API client with user-agent rotation
  - `config.py` — YAML + argparse config loading into dataclasses
  - `service.py` — async monitoring loop, jittered sleep, notifier dispatch, signal handling
  - `notifiers/` — `Notifier` protocol, `LogNotifier` (working), `EmailNotifier` (stub)
- `tests/` — pytest test suite
  - `conftest.py` — `checker`/`make_checker` fixtures, `build_fulfillment_response`/`build_store_option` helpers
  - `test_target_checker.py` — end-to-end tests for `TargetChecker` using `respx` HTTP mocking
- `config.yaml` — runtime config (not committed with real store IDs)

## Testing conventions

- Test framework: pytest with pytest-asyncio (`asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed)
- HTTP mocking: `respx` (intercepts at httpx transport layer). Use the `@respx.mock` decorator on each test.
- Fixtures are in `tests/conftest.py`. Use `make_checker()` for custom params, `checker` for defaults.
- Response builders (`build_fulfillment_response`, `build_store_option`) are plain functions in conftest, imported directly in test files.
- Test classes group by concern: `TestTargetCheckerRequest`, `TestTargetCheckerInStock`, `TestTargetCheckerOutOfStock`, `TestTargetCheckerErrors`, `TestTargetCheckerMalformedResponse`.
- Use `pytest.mark.parametrize` for testing multiple similar cases (HTTP status codes, exception types).

## Code style

- Python 3.11+ (union types use `X | Y`, not `Optional[X]`)
- Async throughout — checkers and notifiers are async
- No type checker configured; use type annotations but don't add them to code you didn't change
- Keep changes minimal. Don't refactor surrounding code or add docstrings where none exist.

## Adding a new checker

1. Create `stock_checker/checkers/<store>.py` implementing the `Checker` protocol (async `check() -> StockStatus`)
2. Register it in `service.py:create_checker()`
3. Add a corresponding `type` value for `config.yaml`
4. Add tests in `tests/test_<store>_checker.py` following the same pattern as `test_target_checker.py`

## Adding a new notifier

1. Create `stock_checker/notifiers/<type>.py` implementing the `Notifier` protocol
2. Register it in `service.py:create_notifiers()`
3. Add a corresponding `type` value for `config.yaml`

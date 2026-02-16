# CLAUDE.md

## Overview

A stock monitoring service that periodically checks product availability at retail stores and sends notifications on restock events. Currently used to track baby formula (Kendamil) availability at Target and Walmart. The architecture has two extension points: **checkers** (poll a store's API/website for stock status) and **notifiers** (alert users when a product comes back in stock).

The service is async throughout. It spawns one monitoring task per product/store combination, each running an independent polling loop with jittered sleep to avoid thundering herd. Notifications fire only on `OUT_OF_STOCK -> IN_STOCK` transitions.

Key design decisions:
- `Checker` and `Notifier` are Python Protocols (structural typing) — no inheritance required, just match the method signature.
- `RetryChecker` is a decorator that wraps any checker with exponential backoff, applied automatically by the service.
- Configuration is layered: YAML file defaults, CLI argument overrides, converted to dataclasses.

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
  - `checkers/base.py` — `StockStatus` enum and `Checker` protocol
  - `checkers/retry.py` — `RetryChecker` decorator (exponential backoff)
  - `checkers/<store>.py` — store-specific checker implementations
  - `notifiers/base.py` — `Notifier` protocol
  - `notifiers/<type>.py` — notifier implementations
  - `config.py` — YAML + argparse config loading into dataclasses
  - `service.py` — async monitoring loop, jittered sleep, notifier dispatch, signal handling
- `tests/` — pytest test suite
  - `conftest.py` — shared fixtures and helpers
  - `test_<store>_checker.py` — per-checker test files
- `config.yaml` — runtime config (not committed with real store IDs)

## Testing conventions

- Test framework: pytest with pytest-asyncio (`asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed)
- HTTP mocking: `unittest.mock.patch` on `AsyncSession` from curl_cffi. Use `@patch("stock_checker.checkers.<module>.AsyncSession")` decorator on each test. Set up via `mock_session_cls.return_value.__aenter__.return_value = mock_session`.
- Mock responses: use `make_mock_response()` from conftest (supports `status_code`, `text`, `json_data`).
- Fixtures are in `tests/conftest.py`. Use `make_checker()` for custom params, `checker` for defaults.
- Test classes group by concern (e.g. `TestXxxInStock`, `TestXxxOutOfStock`, `TestXxxErrors`, `TestXxxMalformedResponse`).
- Use `pytest.mark.parametrize` for testing multiple similar cases (HTTP status codes, exception types).

## Code style

- Python 3.11+ (union types use `X | Y`, not `Optional[X]`)
- Async throughout — checkers and notifiers are async. `curl_cffi` is used for HTTP requests because its browser impersonation bypasses bot detection; `aiohttp` is only used for the optional status page.
- No type checker configured; use type annotations but don't add them to code you didn't change
- Keep changes minimal. Don't refactor surrounding code or add docstrings where none exist.

## Adding a new checker

1. Create `stock_checker/checkers/<store>.py` implementing the `Checker` protocol (async `check() -> StockStatus`). See `checkers/base.py` for the protocol definition. Checkers must return `StockStatus.ERROR` on failure instead of raising exceptions.
2. Add a `StoreConfig` subclass in `config.py` with a `product_id` property and any store-specific fields. Wire it into `_build_store_config()`.
3. Register the checker in `service.py:create_checker()`.
4. Add tests in `tests/test_<store>_checker.py` following the same pattern as existing checker tests.

## Adding a new notifier

1. Create `stock_checker/notifiers/<type>.py` implementing the `Notifier` protocol (async `notify(product_key, product_name, previous, current) -> None`). See `notifiers/base.py` for the protocol definition.
2. Register it in `service.py:create_notifiers()`.
3. Add a corresponding `type` value in the `notifications` section of `config.yaml`.

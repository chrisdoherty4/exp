# stock-checker

Async product availability monitor for retail stores. Currently supports Target via the Redsky API.

Polls Target's fulfillment API on a jittered interval, detects stock status changes, and sends notifications when items come back in stock.

## Requirements

- Python 3.11+

## Setup

```bash
make install
```

Or manually:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Configuration

Copy and edit `config.yaml`:

```yaml
products:
  - name: "Kendamil Goat Infant Powder Formula"
    stores:
      - type: target
        tcin: "88379079"        # Target item number (from product URL)
        store_id: "3991"        # Your local Target store ID
        zip: "55401"            # Your zip code

polling:
  base_interval_seconds: 900    # 15 minutes
  jitter_factor: 0.5            # +/-50% randomization

notifications:
  - type: log                   # Logs to stdout (always enabled)

# proxy:
#   url: "http://user:pass@host:port"
```

### Finding Target product info

- **tcin**: The numeric ID in the Target product URL (e.g., `target.com/p/-/A-88379079` -> `88379079`)
- **store_id**: Find via Target's store locator or browser dev tools

## Usage

Continuous monitoring:

```bash
make run
```

Single check:

```bash
make run-once
```

### CLI options

```
--config PATH      Config file path (default: config.yaml)
--interval SECS    Override polling interval
--jitter FACTOR    Override jitter factor (0.0-1.0)
--log-file PATH    Write logs to file instead of stdout
--log-level LEVEL  DEBUG, INFO, WARNING, or ERROR
--once             Check once and exit
```

## Architecture

```
stock_checker/
  __main__.py          Entry point
  main.py              CLI setup, logging, asyncio.run
  config.py            YAML + CLI argument loading
  service.py           Async monitoring loop with jittered polling
  checkers/
    base.py            StockStatus enum, Checker protocol
    target.py          TargetChecker — Redsky API client
  notifiers/
    base.py            Notifier protocol
    log.py             LogNotifier — logs restock alerts to stdout
    email.py           EmailNotifier — stub (not implemented)
```

### How it works

1. Loads config from YAML, merges CLI overrides
2. Creates a `TargetChecker` per product/store combination
3. Each checker runs in its own `asyncio.Task`, polling on a jittered interval
4. On each poll, `TargetChecker.check()` hits the Redsky fulfillment API and parses the response
5. Fulfillment is checked across four channels: shipping, order pickup, in-store only, and scheduled delivery
6. If the `sold_out` flag is set, the item is immediately marked OUT_OF_STOCK regardless of channel availability
7. Status transitions (OUT_OF_STOCK -> IN_STOCK) trigger notifications
8. Consecutive errors are tracked; a warning is logged after 5 failures in a row
9. User-Agent headers rotate across requests to reduce fingerprinting

## Testing

```bash
make test
```

Verbose output:

```bash
make test-v
```

Tests use `respx` to mock HTTP at the `httpx` transport layer, so the full `AsyncClient` machinery (URL construction, params, headers, `raise_for_status()`) runs in every test. No network calls are made.

### Test coverage

- **Request verification** — correct URL, query params, headers, user-agent rotation
- **In-stock paths** — shipping, order pickup, in-store only, scheduled delivery, multiple channels
- **Out-of-stock paths** — all unavailable, sold_out flag, sold_out overriding in-stock channels
- **Error handling** — HTTP 4xx/5xx, network errors (timeouts, connection failures), unexpected exceptions
- **Malformed responses** — empty JSON, missing keys, null values, empty fulfillment object

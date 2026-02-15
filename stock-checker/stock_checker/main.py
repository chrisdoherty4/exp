import asyncio
import logging
import sys

from stock_checker.config import load_config
from stock_checker.service import run


def setup_logging(log_level: str, log_file: str | None) -> None:
    handlers: list[logging.Handler] = []

    if log_file:
        handlers.append(logging.FileHandler(log_file))
    else:
        handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def main() -> None:
    config = load_config()
    setup_logging(config.log_level, config.log_file)

    logger = logging.getLogger(__name__)
    logger.info("Starting stock checker")
    logger.info(
        "Polling: interval=%ds, jitter=%.1f",
        config.polling.base_interval_seconds,
        config.polling.jitter_factor,
    )
    logger.info("Products: %d", len(config.products))
    logger.info("Mode: %s", "single run" if config.once else "continuous")
    if config.proxy_url:
        logger.info("Proxy: configured")

    asyncio.run(run(config))


if __name__ == "__main__":
    main()

import asyncio
import logging
import random
import signal
from datetime import datetime, timezone

from curl_cffi.requests import AsyncSession

from stock_checker.checkers.base import Checker, StockStatus
from stock_checker.checkers.retry import RetryChecker
from stock_checker.checkers.target import TargetChecker
from stock_checker.checkers.walmart import WalmartChecker
from stock_checker.config import Config, StoreConfig, TargetStoreConfig, WalmartStoreConfig
from stock_checker.notifiers.base import Notifier
from stock_checker.notifiers.email import EmailNotifier
from stock_checker.notifiers.log import LogNotifier
from stock_checker.statuspage import StatusBoard, StoreStatus, start_status_server

logger = logging.getLogger(__name__)

CONSECUTIVE_ERROR_THRESHOLD = 5


def jittered_sleep(base_interval: float, jitter_factor: float) -> float:
    return base_interval + random.uniform(-jitter_factor, jitter_factor) * base_interval


def create_checker(store: StoreConfig, session: AsyncSession, product_name: str = "") -> Checker:
    if isinstance(store, TargetStoreConfig):
        checker = TargetChecker(
            tcin=store.tcin,
            store_id=store.store_id,
            zip_code=store.zip,
            session=session,
            product_name=product_name,
        )
        return RetryChecker(checker)
    if isinstance(store, WalmartStoreConfig):
        checker = WalmartChecker(
            item_id=store.item_id,
            store_id=store.store_id,
            session=session,
            product_name=product_name,
        )
        return RetryChecker(checker)
    raise ValueError(f"Unknown store config: {type(store).__name__}")


def create_notifiers(config: Config) -> list[Notifier]:
    notifiers: list[Notifier] = []
    for n in config.notifications:
        if n.type == "log":
            notifiers.append(LogNotifier())
        elif n.type == "email":
            notifiers.append(EmailNotifier(recipients=n.recipients))
        else:
            logger.warning("Unknown notifier type: %s", n.type)
    return notifiers


async def monitor(
    checker: Checker,
    product_key: str,
    product_name: str,
    notifiers: list[Notifier],
    config: Config,
    store_status: StoreStatus | None = None,
) -> None:
    consecutive_errors = 0

    def _update_status(status: StockStatus) -> None:
        if store_status is not None:
            store_status.status = status
            store_status.last_checked = datetime.now(timezone.utc)

    # First check establishes baseline — no notification.
    current = await checker.check()
    _update_status(current)
    if current == StockStatus.ERROR:
        consecutive_errors = 1
        logger.warning("[%s] Initial check returned ERROR", product_key)
    else:
        logger.info("[%s] Initial status: %s", product_key, current.value)

    previous = current

    if config.once:
        return

    while True:
        sleep = jittered_sleep(
            config.polling.base_interval_seconds,
            config.polling.jitter_factor,
        )
        logger.info("[%s] Next check in %.0fs", product_key, sleep)
        await asyncio.sleep(sleep)

        current = await checker.check()
        _update_status(current)

        if current == StockStatus.ERROR:
            consecutive_errors += 1
            if consecutive_errors > CONSECUTIVE_ERROR_THRESHOLD:
                logger.error(
                    "[%s] Checker has failed %d consecutive times — it may be broken",
                    product_key,
                    consecutive_errors,
                )
            continue

        consecutive_errors = 0

        if previous != current:
            logger.info(
                "[%s] Status changed: %s -> %s",
                product_key,
                previous.value,
                current.value,
            )

            if previous == StockStatus.OUT_OF_STOCK and current == StockStatus.IN_STOCK:
                for notifier in notifiers:
                    try:
                        await notifier.notify(product_key, product_name, previous, current)
                    except Exception:
                        logger.exception("Notifier %s failed for %s", type(notifier).__name__, product_key)

            if previous == StockStatus.IN_STOCK and current == StockStatus.OUT_OF_STOCK:
                logger.info("[%s] Now out of stock", product_key)

        previous = current


async def run(config: Config) -> None:
    notifiers = create_notifiers(config)

    proxies = {"https": config.proxy_url} if config.proxy_url else None
    session = AsyncSession(impersonate="chrome", proxies=proxies)

    board: StatusBoard = {}
    tasks: list[asyncio.Task] = []
    for product in config.products:
        for store in product.stores:
            checker = create_checker(store, session=session, product_name=product.name)
            key = f"{store.type}:{store.product_id}"

            ss = StoreStatus(
                store_type=store.type,
                store_id=store.store_id,
                product_id=store.product_id,
            )
            board.setdefault(product.name, []).append(ss)

            task = asyncio.create_task(
                monitor(checker, key, product.name, notifiers, config, store_status=ss),
                name=f"monitor-{key}",
            )
            tasks.append(task)

    if not tasks:
        logger.error("No products/stores configured. Nothing to monitor.")
        await session.close()
        return

    runner = None
    if config.status_page.enabled:
        runner = await start_status_server(
            board,
            host=config.status_page.host,
            port=config.status_page.port,
        )
        logger.info(
            "Status page running at http://%s:%d",
            config.status_page.host,
            config.status_page.port,
        )

    logger.info("Started %d monitoring task(s)", len(tasks))

    loop = asyncio.get_running_loop()

    def _signal_handler() -> None:
        logger.info("Received shutdown signal, cancelling tasks...")
        for t in tasks:
            t.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        pass
    finally:
        if runner is not None:
            await runner.cleanup()
        await session.close()
        logger.info("Shut down cleanly")

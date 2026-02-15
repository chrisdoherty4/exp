import logging

from stock_checker.checkers.base import StockStatus

logger = logging.getLogger(__name__)


class LogNotifier:
    async def notify(
        self,
        product_key: str,
        product_name: str,
        previous: StockStatus,
        current: StockStatus,
    ) -> None:
        logger.warning(
            "RESTOCK ALERT: %s [%s] is now %s (was %s)",
            product_name,
            product_key,
            current.value,
            previous.value,
        )

import logging

from stock_checker.checkers.base import StockStatus

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Stub email notifier — not yet implemented."""

    def __init__(self, recipients: list[str]) -> None:
        self.recipients = recipients

    async def notify(
        self,
        product_key: str,
        product_name: str,
        previous: StockStatus,
        current: StockStatus,
    ) -> None:
        logger.info(
            "Email notifier not yet implemented. Would notify %s about %s [%s]: %s -> %s",
            self.recipients,
            product_name,
            product_key,
            previous.value,
            current.value,
        )

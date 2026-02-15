from typing import Protocol

from stock_checker.checkers.base import StockStatus


class Notifier(Protocol):
    async def notify(
        self,
        product_key: str,
        product_name: str,
        previous: StockStatus,
        current: StockStatus,
    ) -> None: ...

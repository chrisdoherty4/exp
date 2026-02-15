import asyncio
import logging

from stock_checker.checkers.base import Checker, StockStatus

logger = logging.getLogger(__name__)


class RetryChecker:
    """Wraps any Checker with exponential-backoff retries on ERROR results."""

    def __init__(
        self,
        checker: Checker,
        max_retries: int = 5,
        base_delay: float = 1.0,
    ) -> None:
        self._checker = checker
        self._max_retries = max_retries
        self._base_delay = base_delay

    async def check(self) -> StockStatus:
        for attempt in range(1 + self._max_retries):
            result = await self._checker.check()
            if result != StockStatus.ERROR:
                return result
            if attempt < self._max_retries:
                delay = self._base_delay * (2 ** attempt)
                logger.warning(
                    "Check returned ERROR (attempt %d/%d), retrying in %.1fs",
                    attempt + 1,
                    1 + self._max_retries,
                    delay,
                )
                await asyncio.sleep(delay)
        logger.error(
            "Check failed after %d attempt(s), returning ERROR",
            1 + self._max_retries,
        )
        return StockStatus.ERROR

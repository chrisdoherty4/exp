from unittest.mock import AsyncMock, patch

import pytest

from stock_checker.checkers.base import StockStatus
from stock_checker.checkers.retry import RetryChecker


def make_fake_checker(*results: StockStatus) -> AsyncMock:
    checker = AsyncMock()
    checker.check = AsyncMock(side_effect=list(results))
    return checker


# ---------------------------------------------------------------------------
# TestRetryCheckerSuccess — Returns immediately on non-ERROR
# ---------------------------------------------------------------------------


class TestRetryCheckerSuccess:
    async def test_returns_in_stock_without_retry(self):
        inner = make_fake_checker(StockStatus.IN_STOCK)
        retry = RetryChecker(inner, max_retries=3, base_delay=0.0)

        result = await retry.check()

        assert result == StockStatus.IN_STOCK
        assert inner.check.call_count == 1

    async def test_returns_out_of_stock_without_retry(self):
        inner = make_fake_checker(StockStatus.OUT_OF_STOCK)
        retry = RetryChecker(inner, max_retries=3, base_delay=0.0)

        result = await retry.check()

        assert result == StockStatus.OUT_OF_STOCK
        assert inner.check.call_count == 1

    async def test_returns_unknown_without_retry(self):
        inner = make_fake_checker(StockStatus.UNKNOWN)
        retry = RetryChecker(inner, max_retries=3, base_delay=0.0)

        result = await retry.check()

        assert result == StockStatus.UNKNOWN
        assert inner.check.call_count == 1


# ---------------------------------------------------------------------------
# TestRetryCheckerRetries — Retries on ERROR then succeeds
# ---------------------------------------------------------------------------


class TestRetryCheckerRetries:
    async def test_succeeds_on_second_attempt(self):
        inner = make_fake_checker(StockStatus.ERROR, StockStatus.IN_STOCK)
        retry = RetryChecker(inner, max_retries=3, base_delay=0.0)

        result = await retry.check()

        assert result == StockStatus.IN_STOCK
        assert inner.check.call_count == 2

    async def test_succeeds_on_last_attempt(self):
        inner = make_fake_checker(
            StockStatus.ERROR,
            StockStatus.ERROR,
            StockStatus.ERROR,
            StockStatus.OUT_OF_STOCK,
        )
        retry = RetryChecker(inner, max_retries=3, base_delay=0.0)

        result = await retry.check()

        assert result == StockStatus.OUT_OF_STOCK
        assert inner.check.call_count == 4


# ---------------------------------------------------------------------------
# TestRetryCheckerExhaustion — All retries fail
# ---------------------------------------------------------------------------


class TestRetryCheckerExhaustion:
    async def test_returns_error_after_exhausting_retries(self):
        inner = make_fake_checker(
            StockStatus.ERROR,
            StockStatus.ERROR,
            StockStatus.ERROR,
            StockStatus.ERROR,
        )
        retry = RetryChecker(inner, max_retries=3, base_delay=0.0)

        result = await retry.check()

        assert result == StockStatus.ERROR
        assert inner.check.call_count == 4

    async def test_max_retries_zero_means_no_retry(self):
        inner = make_fake_checker(StockStatus.ERROR)
        retry = RetryChecker(inner, max_retries=0, base_delay=0.0)

        result = await retry.check()

        assert result == StockStatus.ERROR
        assert inner.check.call_count == 1


# ---------------------------------------------------------------------------
# TestRetryCheckerBackoff — Exponential delay between retries
# ---------------------------------------------------------------------------


class TestRetryCheckerBackoff:
    @patch("stock_checker.checkers.retry.asyncio.sleep", new_callable=AsyncMock)
    async def test_exponential_backoff_delays(self, mock_sleep):
        inner = make_fake_checker(
            StockStatus.ERROR,
            StockStatus.ERROR,
            StockStatus.ERROR,
            StockStatus.ERROR,
        )
        retry = RetryChecker(inner, max_retries=3, base_delay=1.0)

        await retry.check()

        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0, 4.0]

    @patch("stock_checker.checkers.retry.asyncio.sleep", new_callable=AsyncMock)
    async def test_no_sleep_when_first_attempt_succeeds(self, mock_sleep):
        inner = make_fake_checker(StockStatus.IN_STOCK)
        retry = RetryChecker(inner, max_retries=3, base_delay=1.0)

        await retry.check()

        mock_sleep.assert_not_called()

    @patch("stock_checker.checkers.retry.asyncio.sleep", new_callable=AsyncMock)
    async def test_custom_base_delay(self, mock_sleep):
        inner = make_fake_checker(
            StockStatus.ERROR,
            StockStatus.ERROR,
            StockStatus.IN_STOCK,
        )
        retry = RetryChecker(inner, max_retries=3, base_delay=0.5)

        await retry.check()

        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [0.5, 1.0]

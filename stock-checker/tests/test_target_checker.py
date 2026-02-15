import httpx
import pytest
import respx

from stock_checker.checkers.base import StockStatus
from stock_checker.checkers.target import API_KEY, REDSKY_URL, USER_AGENTS

from .conftest import (
    DEFAULT_STORE_ID,
    DEFAULT_TCIN,
    DEFAULT_ZIP,
    build_fulfillment_response,
    build_store_option,
)


# ---------------------------------------------------------------------------
# TestTargetCheckerRequest — Verify correct HTTP request
# ---------------------------------------------------------------------------


class TestTargetCheckerRequest:
    @respx.mock
    async def test_sends_correct_url_params_and_headers(self, checker):
        route = respx.get(REDSKY_URL).mock(
            return_value=httpx.Response(200, json=build_fulfillment_response())
        )

        await checker.check()

        assert route.called
        request = route.calls.last.request

        assert request.url.params["key"] == API_KEY
        assert request.url.params["tcin"] == DEFAULT_TCIN
        assert request.url.params["store_id"] == DEFAULT_STORE_ID
        assert request.url.params["zip"] == DEFAULT_ZIP

        assert request.headers["accept"] == "application/json"
        assert request.headers["user-agent"] == USER_AGENTS[0]

    @respx.mock
    async def test_user_agent_rotates_on_successive_calls(self, checker):
        respx.get(REDSKY_URL).mock(
            return_value=httpx.Response(200, json=build_fulfillment_response())
        )

        await checker.check()
        await checker.check()

        first_ua = respx.calls[0].request.headers["user-agent"]
        second_ua = respx.calls[1].request.headers["user-agent"]

        assert first_ua == USER_AGENTS[0]
        assert second_ua == USER_AGENTS[1]
        assert first_ua != second_ua


# ---------------------------------------------------------------------------
# TestTargetCheckerInStock — Happy-path fulfillment
# ---------------------------------------------------------------------------


class TestTargetCheckerInStock:
    @respx.mock
    async def test_in_stock_via_shipping(self, checker):
        respx.get(REDSKY_URL).mock(
            return_value=httpx.Response(
                200,
                json=build_fulfillment_response(shipping_status="IN_STOCK", shipping_qty=5),
            )
        )
        assert await checker.check() == StockStatus.IN_STOCK

    @respx.mock
    async def test_in_stock_via_order_pickup(self, checker):
        respx.get(REDSKY_URL).mock(
            return_value=httpx.Response(
                200,
                json=build_fulfillment_response(
                    store_options=[build_store_option(order_pickup_status="IN_STOCK", location_qty=3)],
                ),
            )
        )
        assert await checker.check() == StockStatus.IN_STOCK

    @respx.mock
    async def test_in_stock_via_in_store_only(self, checker):
        respx.get(REDSKY_URL).mock(
            return_value=httpx.Response(
                200,
                json=build_fulfillment_response(
                    store_options=[build_store_option(in_store_only_status="IN_STOCK", location_qty=2)],
                ),
            )
        )
        assert await checker.check() == StockStatus.IN_STOCK

    @respx.mock
    async def test_in_stock_via_scheduled_delivery(self, checker):
        respx.get(REDSKY_URL).mock(
            return_value=httpx.Response(
                200,
                json=build_fulfillment_response(delivery_status="IN_STOCK"),
            )
        )
        assert await checker.check() == StockStatus.IN_STOCK

    @respx.mock
    async def test_in_stock_multiple_channels(self, checker):
        respx.get(REDSKY_URL).mock(
            return_value=httpx.Response(
                200,
                json=build_fulfillment_response(
                    shipping_status="IN_STOCK",
                    shipping_qty=5,
                    store_options=[build_store_option(order_pickup_status="IN_STOCK", location_qty=3)],
                ),
            )
        )
        assert await checker.check() == StockStatus.IN_STOCK


# ---------------------------------------------------------------------------
# TestTargetCheckerOutOfStock — Out-of-stock paths
# ---------------------------------------------------------------------------


class TestTargetCheckerOutOfStock:
    @respx.mock
    async def test_out_of_stock_all_unavailable(self, checker):
        respx.get(REDSKY_URL).mock(
            return_value=httpx.Response(200, json=build_fulfillment_response())
        )
        assert await checker.check() == StockStatus.OUT_OF_STOCK

    @respx.mock
    async def test_out_of_stock_sold_out_flag(self, checker):
        respx.get(REDSKY_URL).mock(
            return_value=httpx.Response(
                200, json=build_fulfillment_response(sold_out=True)
            )
        )
        assert await checker.check() == StockStatus.OUT_OF_STOCK

    @respx.mock
    async def test_sold_out_overrides_in_stock_channels(self, checker):
        respx.get(REDSKY_URL).mock(
            return_value=httpx.Response(
                200,
                json=build_fulfillment_response(
                    sold_out=True,
                    shipping_status="IN_STOCK",
                    shipping_qty=10,
                ),
            )
        )
        assert await checker.check() == StockStatus.OUT_OF_STOCK


# ---------------------------------------------------------------------------
# TestTargetCheckerErrors — HTTP and network errors
# ---------------------------------------------------------------------------


class TestTargetCheckerErrors:
    @respx.mock
    @pytest.mark.parametrize("status_code", [400, 403, 404, 429, 500, 502, 503])
    async def test_http_error_status_returns_error(self, checker, status_code):
        respx.get(REDSKY_URL).mock(
            return_value=httpx.Response(status_code)
        )
        assert await checker.check() == StockStatus.ERROR

    @respx.mock
    @pytest.mark.parametrize(
        "exc",
        [
            httpx.ConnectTimeout("timed out"),
            httpx.ConnectError("connection refused"),
            httpx.ReadTimeout("read timed out"),
        ],
        ids=["ConnectTimeout", "ConnectError", "ReadTimeout"],
    )
    async def test_network_errors_return_error(self, checker, exc):
        respx.get(REDSKY_URL).mock(side_effect=exc)
        assert await checker.check() == StockStatus.ERROR

    @respx.mock
    async def test_unexpected_exception_returns_error(self, checker):
        respx.get(REDSKY_URL).mock(side_effect=RuntimeError("boom"))
        assert await checker.check() == StockStatus.ERROR


# ---------------------------------------------------------------------------
# TestTargetCheckerMalformedResponse — Bad JSON shapes
# ---------------------------------------------------------------------------


class TestTargetCheckerMalformedResponse:
    @respx.mock
    async def test_empty_json_returns_error(self, checker):
        respx.get(REDSKY_URL).mock(
            return_value=httpx.Response(200, json={})
        )
        assert await checker.check() == StockStatus.ERROR

    @respx.mock
    async def test_missing_product_returns_error(self, checker):
        respx.get(REDSKY_URL).mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        assert await checker.check() == StockStatus.ERROR

    @respx.mock
    async def test_missing_fulfillment_returns_error(self, checker):
        respx.get(REDSKY_URL).mock(
            return_value=httpx.Response(200, json={"data": {"product": {}}})
        )
        assert await checker.check() == StockStatus.ERROR

    @respx.mock
    async def test_null_product_returns_error(self, checker):
        respx.get(REDSKY_URL).mock(
            return_value=httpx.Response(200, json={"data": {"product": None}})
        )
        assert await checker.check() == StockStatus.ERROR

    @respx.mock
    async def test_empty_fulfillment_returns_out_of_stock(self, checker):
        respx.get(REDSKY_URL).mock(
            return_value=httpx.Response(
                200,
                json={"data": {"product": {"fulfillment": {}}}},
            )
        )
        assert await checker.check() == StockStatus.OUT_OF_STOCK

import pytest

from curl_cffi.requests.errors import RequestsError
from stock_checker.checkers.base import StockStatus

from .conftest import (
    build_fulfillment_response,
    build_store_option,
    make_mock_response,
)


# ---------------------------------------------------------------------------
# TestTargetCheckerInStock — Happy-path fulfillment
# ---------------------------------------------------------------------------


class TestTargetCheckerInStock:
    async def test_in_stock_via_shipping(self, mock_session, checker):
        mock_session.get.return_value = make_mock_response(
            200, json_data=build_fulfillment_response(shipping_status="IN_STOCK", shipping_qty=5)
        )
        assert await checker.check() == StockStatus.IN_STOCK

    async def test_in_stock_via_order_pickup(self, mock_session, checker):
        mock_session.get.return_value = make_mock_response(
            200,
            json_data=build_fulfillment_response(
                store_options=[build_store_option(order_pickup_status="IN_STOCK", location_qty=3)],
            ),
        )
        assert await checker.check() == StockStatus.IN_STOCK

    async def test_in_stock_via_in_store_only(self, mock_session, checker):
        mock_session.get.return_value = make_mock_response(
            200,
            json_data=build_fulfillment_response(
                store_options=[build_store_option(in_store_only_status="IN_STOCK", location_qty=2)],
            ),
        )
        assert await checker.check() == StockStatus.IN_STOCK

    async def test_in_stock_via_scheduled_delivery(self, mock_session, checker):
        mock_session.get.return_value = make_mock_response(
            200, json_data=build_fulfillment_response(delivery_status="IN_STOCK")
        )
        assert await checker.check() == StockStatus.IN_STOCK

    async def test_in_stock_multiple_channels(self, mock_session, checker):
        mock_session.get.return_value = make_mock_response(
            200,
            json_data=build_fulfillment_response(
                shipping_status="IN_STOCK",
                shipping_qty=5,
                store_options=[build_store_option(order_pickup_status="IN_STOCK", location_qty=3)],
            ),
        )
        assert await checker.check() == StockStatus.IN_STOCK


# ---------------------------------------------------------------------------
# TestTargetCheckerOutOfStock — Out-of-stock paths
# ---------------------------------------------------------------------------


class TestTargetCheckerOutOfStock:
    async def test_out_of_stock_all_unavailable(self, mock_session, checker):
        mock_session.get.return_value = make_mock_response(200, json_data=build_fulfillment_response())
        assert await checker.check() == StockStatus.OUT_OF_STOCK

    async def test_out_of_stock_sold_out_flag(self, mock_session, checker):
        mock_session.get.return_value = make_mock_response(
            200, json_data=build_fulfillment_response(sold_out=True)
        )
        assert await checker.check() == StockStatus.OUT_OF_STOCK

    async def test_sold_out_overrides_in_stock_channels(self, mock_session, checker):
        mock_session.get.return_value = make_mock_response(
            200,
            json_data=build_fulfillment_response(
                sold_out=True,
                shipping_status="IN_STOCK",
                shipping_qty=10,
            ),
        )
        assert await checker.check() == StockStatus.OUT_OF_STOCK


# ---------------------------------------------------------------------------
# TestTargetCheckerErrors — HTTP and network errors
# ---------------------------------------------------------------------------


class TestTargetCheckerErrors:
    @pytest.mark.parametrize("status_code", [400, 403, 404, 429, 500, 502, 503])
    async def test_http_error_status_returns_error(self, mock_session, checker, status_code):
        mock_session.get.return_value = make_mock_response(status_code)
        assert await checker.check() == StockStatus.ERROR

    async def test_network_error_returns_error(self, mock_session, checker):
        mock_session.get.side_effect = RequestsError("connection refused")
        assert await checker.check() == StockStatus.ERROR

    async def test_unexpected_exception_returns_error(self, mock_session, checker):
        mock_session.get.side_effect = RuntimeError("boom")
        assert await checker.check() == StockStatus.ERROR


# ---------------------------------------------------------------------------
# TestTargetCheckerMalformedResponse — Bad JSON shapes
# ---------------------------------------------------------------------------


class TestTargetCheckerMalformedResponse:
    async def test_empty_json_returns_error(self, mock_session, checker):
        mock_session.get.return_value = make_mock_response(200, json_data={})
        assert await checker.check() == StockStatus.ERROR

    async def test_missing_product_returns_error(self, mock_session, checker):
        mock_session.get.return_value = make_mock_response(200, json_data={"data": {}})
        assert await checker.check() == StockStatus.ERROR

    async def test_missing_fulfillment_returns_error(self, mock_session, checker):
        mock_session.get.return_value = make_mock_response(200, json_data={"data": {"product": {}}})
        assert await checker.check() == StockStatus.ERROR

    async def test_null_product_returns_error(self, mock_session, checker):
        mock_session.get.return_value = make_mock_response(200, json_data={"data": {"product": None}})
        assert await checker.check() == StockStatus.ERROR

    async def test_empty_fulfillment_returns_out_of_stock(self, mock_session, checker):
        mock_session.get.return_value = make_mock_response(
            200, json_data={"data": {"product": {"fulfillment": {}}}}
        )
        assert await checker.check() == StockStatus.OUT_OF_STOCK

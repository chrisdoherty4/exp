import pytest

from curl_cffi.requests.errors import RequestsError
from stock_checker.checkers.base import StockStatus

from .conftest import (
    build_walmart_next_data,
    build_walmart_page,
    build_walmart_pickup_option,
    make_mock_response,
)


# ---------------------------------------------------------------------------
# TestWalmartCheckerInStock — Pickup available scenarios
# ---------------------------------------------------------------------------


class TestWalmartCheckerInStock:
    async def test_in_stock_via_pickup(self, mock_session, walmart_checker):
        page = build_walmart_page(
            build_walmart_next_data([
                build_walmart_pickup_option(availability_status="IN_STOCK", option_type="PICKUP"),
            ])
        )
        mock_session.get.return_value = make_mock_response(200, text=page)
        assert await walmart_checker.check() == StockStatus.IN_STOCK

    async def test_in_stock_via_in_store(self, mock_session, walmart_checker):
        page = build_walmart_page(
            build_walmart_next_data([
                build_walmart_pickup_option(availability_status="IN_STOCK", option_type="IN_STORE"),
            ])
        )
        mock_session.get.return_value = make_mock_response(200, text=page)
        assert await walmart_checker.check() == StockStatus.IN_STOCK

    async def test_in_stock_pickup_among_multiple_options(self, mock_session, walmart_checker):
        page = build_walmart_page(
            build_walmart_next_data([
                build_walmart_pickup_option(availability_status="OUT_OF_STOCK", option_type="SHIPPING"),
                build_walmart_pickup_option(availability_status="IN_STOCK", option_type="PICKUP"),
            ])
        )
        mock_session.get.return_value = make_mock_response(200, text=page)
        assert await walmart_checker.check() == StockStatus.IN_STOCK


# ---------------------------------------------------------------------------
# TestWalmartCheckerOutOfStock — No pickup / unavailable
# ---------------------------------------------------------------------------


class TestWalmartCheckerOutOfStock:
    async def test_out_of_stock_pickup_unavailable(self, mock_session, walmart_checker):
        page = build_walmart_page(
            build_walmart_next_data([
                build_walmart_pickup_option(availability_status="OUT_OF_STOCK", option_type="PICKUP"),
            ])
        )
        mock_session.get.return_value = make_mock_response(200, text=page)
        assert await walmart_checker.check() == StockStatus.OUT_OF_STOCK

    async def test_out_of_stock_shipping_only(self, mock_session, walmart_checker):
        page = build_walmart_page(
            build_walmart_next_data([
                build_walmart_pickup_option(availability_status="IN_STOCK", option_type="SHIPPING"),
            ])
        )
        mock_session.get.return_value = make_mock_response(200, text=page)
        assert await walmart_checker.check() == StockStatus.OUT_OF_STOCK

    async def test_out_of_stock_empty_fulfillment_options(self, mock_session, walmart_checker):
        page = build_walmart_page(build_walmart_next_data([]))
        mock_session.get.return_value = make_mock_response(200, text=page)
        assert await walmart_checker.check() == StockStatus.OUT_OF_STOCK


# ---------------------------------------------------------------------------
# TestWalmartCheckerErrors — HTTP, network, and bot detection errors
# ---------------------------------------------------------------------------


class TestWalmartCheckerErrors:
    @pytest.mark.parametrize("status_code", [400, 403, 404, 429, 500, 502, 503])
    async def test_http_error_status_returns_error(self, mock_session, walmart_checker, status_code):
        mock_session.get.return_value = make_mock_response(status_code)
        assert await walmart_checker.check() == StockStatus.ERROR

    async def test_network_error_returns_error(self, mock_session, walmart_checker):
        mock_session.get.side_effect = RequestsError("connection refused")
        assert await walmart_checker.check() == StockStatus.ERROR

    async def test_unexpected_exception_returns_error(self, mock_session, walmart_checker):
        mock_session.get.side_effect = RuntimeError("boom")
        assert await walmart_checker.check() == StockStatus.ERROR

    async def test_bot_detection_captcha_returns_error(self, mock_session, walmart_checker):
        captcha_html = '<html><body><div id="px-captcha"></div></body></html>'
        mock_session.get.return_value = make_mock_response(200, text=captcha_html)
        assert await walmart_checker.check() == StockStatus.ERROR


# ---------------------------------------------------------------------------
# TestWalmartCheckerMalformedResponse — Bad HTML / JSON shapes
# ---------------------------------------------------------------------------


class TestWalmartCheckerMalformedResponse:
    async def test_no_next_data_script_returns_error(self, mock_session, walmart_checker):
        mock_session.get.return_value = make_mock_response(200, text="<html><body>No data here</body></html>")
        assert await walmart_checker.check() == StockStatus.ERROR

    async def test_invalid_json_in_next_data_returns_error(self, mock_session, walmart_checker):
        html = (
            '<html><body>'
            '<script id="__NEXT_DATA__" type="application/json">{not json}</script>'
            '</body></html>'
        )
        mock_session.get.return_value = make_mock_response(200, text=html)
        assert await walmart_checker.check() == StockStatus.ERROR

    async def test_missing_product_key_returns_error(self, mock_session, walmart_checker):
        page = build_walmart_page({"props": {"pageProps": {"initialData": {"data": {}}}}})
        mock_session.get.return_value = make_mock_response(200, text=page)
        assert await walmart_checker.check() == StockStatus.ERROR

    async def test_missing_fulfillment_options_returns_error(self, mock_session, walmart_checker):
        page = build_walmart_page(
            {"props": {"pageProps": {"initialData": {"data": {"product": {}}}}}}
        )
        mock_session.get.return_value = make_mock_response(200, text=page)
        assert await walmart_checker.check() == StockStatus.ERROR

    async def test_null_product_returns_error(self, mock_session, walmart_checker):
        page = build_walmart_page(
            {"props": {"pageProps": {"initialData": {"data": {"product": None}}}}}
        )
        mock_session.get.return_value = make_mock_response(200, text=page)
        assert await walmart_checker.check() == StockStatus.ERROR

    async def test_empty_next_data_returns_error(self, mock_session, walmart_checker):
        page = build_walmart_page({})
        mock_session.get.return_value = make_mock_response(200, text=page)
        assert await walmart_checker.check() == StockStatus.ERROR

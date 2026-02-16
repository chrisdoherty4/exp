from datetime import datetime, timezone

from aiohttp.test_utils import TestClient, TestServer

from stock_checker.checkers.base import StockStatus
from stock_checker.statuspage import StatusBoard, StoreStatus, render_html, handle_index

from aiohttp import web


# ---------------------------------------------------------------------------
# render_html tests
# ---------------------------------------------------------------------------


class TestRenderHtmlEmptyBoard:
    def test_empty_board_shows_no_products(self):
        html = render_html({})
        assert "No products configured." in html

    def test_empty_board_has_auto_refresh(self):
        html = render_html({})
        assert '<meta http-equiv="refresh" content="30">' in html


class TestRenderHtmlSingleProduct:
    def test_in_stock_product(self):
        board: StatusBoard = {
            "Test Product": [
                StoreStatus(
                    store_type="target",
                    store_id="1234",
                    product_id="999",
                    status=StockStatus.IN_STOCK,
                    last_checked=datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
                ),
            ],
        }
        html = render_html(board)
        assert "Test Product" in html
        assert "IN_STOCK" in html
        assert "target" in html
        assert "1234" in html
        assert "999" in html
        assert "2025-01-15 12:00:00" in html

    def test_out_of_stock_product(self):
        board: StatusBoard = {
            "Test Product": [
                StoreStatus(
                    store_type="walmart",
                    store_id="5678",
                    product_id="111",
                    status=StockStatus.OUT_OF_STOCK,
                ),
            ],
        }
        html = render_html(board)
        assert "OUT_OF_STOCK" in html
        assert "\u2014" in html  # em dash for no last_checked


class TestRenderHtmlMultipleStores:
    def test_multiple_stores_per_product(self):
        board: StatusBoard = {
            "Multi Store Product": [
                StoreStatus(
                    store_type="target",
                    store_id="1111",
                    product_id="aaa",
                    status=StockStatus.IN_STOCK,
                ),
                StoreStatus(
                    store_type="walmart",
                    store_id="2222",
                    product_id="bbb",
                    status=StockStatus.OUT_OF_STOCK,
                ),
            ],
        }
        html = render_html(board)
        assert "target" in html
        assert "walmart" in html
        assert "1111" in html
        assert "2222" in html


class TestRenderHtmlEscaping:
    def test_html_escaping_of_product_names(self):
        board: StatusBoard = {
            '<script>alert("xss")</script>': [
                StoreStatus(
                    store_type="target",
                    store_id="1",
                    product_id="2",
                ),
            ],
        }
        html = render_html(board)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestRenderHtmlAutoRefresh:
    def test_auto_refresh_meta_tag(self):
        board: StatusBoard = {
            "Product": [
                StoreStatus(store_type="t", store_id="1", product_id="2"),
            ],
        }
        html = render_html(board)
        assert '<meta http-equiv="refresh" content="30">' in html


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------


class TestHttpEndpoint:
    async def test_get_returns_200(self):
        board: StatusBoard = {
            "Test Product": [
                StoreStatus(
                    store_type="target",
                    store_id="1234",
                    product_id="999",
                    status=StockStatus.IN_STOCK,
                ),
            ],
        }
        app = web.Application()
        app["board"] = board
        app.router.add_get("/", handle_index)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/")
            assert resp.status == 200
            assert "text/html" in resp.content_type
            text = await resp.text()
            assert "Test Product" in text
            assert "IN_STOCK" in text


# ---------------------------------------------------------------------------
# StoreStatus mutation tests
# ---------------------------------------------------------------------------


class TestStoreStatusMutation:
    def test_updating_store_status_visible_through_board(self):
        ss = StoreStatus(
            store_type="target",
            store_id="1",
            product_id="2",
            status=StockStatus.UNKNOWN,
        )
        board: StatusBoard = {"Product": [ss]}

        ss.status = StockStatus.IN_STOCK
        ss.last_checked = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)

        assert board["Product"][0].status == StockStatus.IN_STOCK
        assert board["Product"][0].last_checked == datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)

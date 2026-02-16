import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from curl_cffi.requests.errors import RequestsError
from stock_checker.checkers.target import TargetChecker
from stock_checker.checkers.walmart import WalmartChecker

# ---------------------------------------------------------------------------
# Mock response helper
# ---------------------------------------------------------------------------


def make_mock_response(status_code: int = 200, text: str = "", json_data: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = RequestsError(f"HTTP {status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Shared session fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    return AsyncMock()


# ---------------------------------------------------------------------------
# Target fixtures
# ---------------------------------------------------------------------------

DEFAULT_TCIN = "12345678"
DEFAULT_STORE_ID = "3991"
DEFAULT_ZIP = "55401"


@pytest.fixture
def make_checker(mock_session):
    def _make(
        tcin: str = DEFAULT_TCIN,
        store_id: str = DEFAULT_STORE_ID,
        zip_code: str = DEFAULT_ZIP,
    ) -> TargetChecker:
        return TargetChecker(
            tcin=tcin,
            store_id=store_id,
            zip_code=zip_code,
            session=mock_session,
            product_name="Test Product",
        )

    return _make


@pytest.fixture
def checker(make_checker):
    return make_checker()


def build_store_option(
    order_pickup_status: str = "UNAVAILABLE",
    in_store_only_status: str = "UNAVAILABLE",
    location_qty: float = 0,
) -> dict:
    return {
        "order_pickup": {"availability_status": order_pickup_status},
        "in_store_only": {"availability_status": in_store_only_status},
        "location_available_to_promise_quantity": location_qty,
    }


def build_fulfillment_response(
    sold_out: bool = False,
    shipping_status: str = "UNAVAILABLE",
    shipping_qty: int = 0,
    store_options: list[dict] | None = None,
    delivery_status: str = "UNAVAILABLE",
) -> dict:
    if store_options is None:
        store_options = [build_store_option()]
    return {
        "data": {
            "product": {
                "fulfillment": {
                    "sold_out": sold_out,
                    "shipping_options": {
                        "availability_status": shipping_status,
                        "available_to_promise_quantity": shipping_qty,
                    },
                    "store_options": store_options,
                    "scheduled_delivery": {
                        "availability_status": delivery_status,
                    },
                }
            }
        }
    }


# ---------------------------------------------------------------------------
# Walmart fixtures
# ---------------------------------------------------------------------------

DEFAULT_WALMART_ITEM_ID = "987654321"
DEFAULT_WALMART_STORE_ID = "5260"


@pytest.fixture
def make_walmart_checker(mock_session):
    def _make(
        item_id: str = DEFAULT_WALMART_ITEM_ID,
        store_id: str = DEFAULT_WALMART_STORE_ID,
    ) -> WalmartChecker:
        return WalmartChecker(
            item_id=item_id,
            store_id=store_id,
            session=mock_session,
            product_name="Test Product",
        )

    return _make


@pytest.fixture
def walmart_checker(make_walmart_checker):
    return make_walmart_checker()


def build_walmart_pickup_option(
    availability_status: str = "OUT_OF_STOCK",
    option_type: str = "PICKUP",
) -> dict:
    return {
        "type": option_type,
        "availabilityStatus": availability_status,
    }


def build_walmart_next_data(
    fulfillment_options: list[dict] | None = None,
) -> dict:
    if fulfillment_options is None:
        fulfillment_options = [build_walmart_pickup_option()]
    return {
        "props": {
            "pageProps": {
                "initialData": {
                    "data": {
                        "product": {
                            "fulfillmentOptions": fulfillment_options,
                        }
                    }
                }
            }
        }
    }


def build_walmart_page(next_data: dict | None = None) -> str:
    if next_data is None:
        next_data = build_walmart_next_data()
    return (
        "<html><head></head><body>"
        '<script id="__NEXT_DATA__" type="application/json" nonce="test">'
        + json.dumps(next_data)
        + "</script></body></html>"
    )

import pytest

from stock_checker.checkers.target import TargetChecker

DEFAULT_TCIN = "12345678"
DEFAULT_STORE_ID = "3991"
DEFAULT_ZIP = "55401"


@pytest.fixture
def make_checker():
    def _make(
        tcin: str = DEFAULT_TCIN,
        store_id: str = DEFAULT_STORE_ID,
        zip_code: str = DEFAULT_ZIP,
        proxy_url: str | None = None,
    ) -> TargetChecker:
        return TargetChecker(
            tcin=tcin,
            store_id=store_id,
            zip_code=zip_code,
            proxy_url=proxy_url,
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

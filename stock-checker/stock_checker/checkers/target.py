import logging

from curl_cffi.requests.errors import RequestsError

from stock_checker.checkers.base import StockStatus

logger = logging.getLogger(__name__)

REDSKY_URL = "https://redsky.target.com/redsky_aggregations/v1/web/product_fulfillment_v1"
API_KEY = "9f36aeafbe60771e321a7cc95a78140772ab3e96"


class TargetChecker:
    def __init__(self, tcin: str, store_id: str, zip_code: str, session, product_name: str = "") -> None:
        self.tcin = tcin
        self.store_id = store_id
        self.zip_code = zip_code
        self._session = session
        self._label = f"'{product_name}' (tcin={tcin}, store={store_id})" if product_name else f"tcin={tcin}, store={store_id}"

    async def check(self) -> StockStatus:
        params = {
            "key": API_KEY,
            "tcin": self.tcin,
            "store_id": self.store_id,
            "zip": self.zip_code,
        }

        try:
            resp = await self._session.get(REDSKY_URL, params=params, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
        except RequestsError as exc:
            logger.error("Target API error for %s: %s", self._label, exc)
            return StockStatus.ERROR
        except Exception as exc:
            logger.error("Unexpected error checking Target %s: %s", self._label, exc)
            return StockStatus.ERROR

        return self._parse_fulfillment(data)

    def _parse_fulfillment(self, data: dict) -> StockStatus:
        try:
            product = data["data"]["product"]
            fulfillment = product["fulfillment"]
        except (KeyError, TypeError):
            logger.error(
                "Unexpected response structure for %s: missing fulfillment data",
                self._label,
            )
            logger.debug("Response data: %s", data)
            return StockStatus.ERROR

        # Quick check: top-level sold_out flag
        if fulfillment.get("sold_out"):
            logger.info("Target %s: OUT_OF_STOCK (sold_out=true)", self._label)
            return StockStatus.OUT_OF_STOCK

        # Check shipping availability
        shipping = fulfillment.get("shipping_options", {})
        shipping_available = shipping.get("availability_status") == "IN_STOCK"
        shipping_qty = shipping.get("available_to_promise_quantity", 0)

        # Check store pickup (order_pickup or in_store_only)
        store_options = fulfillment.get("store_options", [])
        pickup_available = False
        store_qty = 0.0
        for option in store_options:
            store_qty = option.get("location_available_to_promise_quantity", 0)
            status = option.get("order_pickup", {}).get("availability_status")
            if status == "IN_STOCK":
                pickup_available = True
                break
            status = option.get("in_store_only", {}).get("availability_status")
            if status == "IN_STOCK":
                pickup_available = True
                break

        # Check scheduled delivery
        delivery = fulfillment.get("scheduled_delivery", {})
        delivery_available = delivery.get("availability_status") == "IN_STOCK"

        if shipping_available or pickup_available or delivery_available:
            logger.info(
                "Target %s: IN_STOCK (shipping=%s/qty=%.0f, pickup=%s/qty=%.0f, delivery=%s)",
                self._label,
                shipping_available,
                shipping_qty,
                pickup_available,
                store_qty,
                delivery_available,
            )
            return StockStatus.IN_STOCK

        logger.info("Target %s: OUT_OF_STOCK", self._label)
        return StockStatus.OUT_OF_STOCK

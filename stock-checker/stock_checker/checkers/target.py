import logging

import httpx

from stock_checker.checkers.base import StockStatus

logger = logging.getLogger(__name__)

REDSKY_URL = "https://redsky.target.com/redsky_aggregations/v1/web/product_fulfillment_v1"
API_KEY = "9f36aeafbe60771e321a7cc95a78140772ab3e96"
TIMEOUT = 10.0

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class TargetChecker:
    def __init__(self, tcin: str, store_id: str, zip_code: str, proxy_url: str | None = None) -> None:
        self.tcin = tcin
        self.store_id = store_id
        self.zip_code = zip_code
        self.proxy_url = proxy_url
        self._ua_index = 0

    def _next_user_agent(self) -> str:
        ua = USER_AGENTS[self._ua_index % len(USER_AGENTS)]
        self._ua_index += 1
        return ua

    async def check(self) -> StockStatus:
        params = {
            "key": API_KEY,
            "tcin": self.tcin,
            "store_id": self.store_id,
            "zip": self.zip_code,
        }
        headers = {
            "User-Agent": self._next_user_agent(),
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, proxy=self.proxy_url) as client:
                resp = await client.get(REDSKY_URL, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Target API HTTP error for tcin=%s store=%s: %s",
                self.tcin,
                self.store_id,
                exc,
            )
            return StockStatus.ERROR
        except httpx.RequestError as exc:
            logger.error(
                "Target API request error for tcin=%s store=%s: %s",
                self.tcin,
                self.store_id,
                exc,
            )
            return StockStatus.ERROR
        except Exception as exc:
            logger.error(
                "Unexpected error checking Target tcin=%s store=%s: %s",
                self.tcin,
                self.store_id,
                exc,
            )
            return StockStatus.ERROR

        return self._parse_fulfillment(data)

    def _parse_fulfillment(self, data: dict) -> StockStatus:
        try:
            product = data["data"]["product"]
            fulfillment = product["fulfillment"]
        except (KeyError, TypeError):
            logger.error(
                "Unexpected response structure for tcin=%s store=%s: missing fulfillment data",
                self.tcin,
                self.store_id,
            )
            logger.debug("Response data: %s", data)
            return StockStatus.ERROR

        # Quick check: top-level sold_out flag
        if fulfillment.get("sold_out"):
            logger.info("Target tcin=%s store=%s: OUT_OF_STOCK (sold_out=true)", self.tcin, self.store_id)
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
                "Target tcin=%s store=%s: IN_STOCK (shipping=%s/qty=%.0f, pickup=%s/qty=%.0f, delivery=%s)",
                self.tcin,
                self.store_id,
                shipping_available,
                shipping_qty,
                pickup_available,
                store_qty,
                delivery_available,
            )
            return StockStatus.IN_STOCK

        logger.info(
            "Target tcin=%s store=%s: OUT_OF_STOCK",
            self.tcin,
            self.store_id,
        )
        return StockStatus.OUT_OF_STOCK

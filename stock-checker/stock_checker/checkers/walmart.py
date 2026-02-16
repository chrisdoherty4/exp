import json
import logging
import re

from curl_cffi.requests.errors import RequestsError

from stock_checker.checkers.base import StockStatus

logger = logging.getLogger(__name__)

WALMART_URL = "https://www.walmart.com/ip/{item_id}"

NEXT_DATA_RE = re.compile(
    r'<script\s+id="__NEXT_DATA__"\s+type="application/json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)


class WalmartChecker:
    def __init__(self, item_id: str, store_id: str, session, product_name: str = "") -> None:
        self.item_id = item_id
        self.store_id = store_id
        self._session = session
        self._label = f"'{product_name}' (item={item_id}, store={store_id})" if product_name else f"item={item_id}, store={store_id}"

    async def check(self) -> StockStatus:
        url = WALMART_URL.format(item_id=self.item_id)
        params = {"storeId": self.store_id}

        try:
            resp = await self._session.get(url, params=params, timeout=15.0)
            resp.raise_for_status()
            html = resp.text
        except RequestsError as exc:
            logger.error("Walmart error for %s: %s", self._label, exc)
            return StockStatus.ERROR
        except Exception as exc:
            logger.error("Unexpected error checking Walmart %s: %s", self._label, exc)
            return StockStatus.ERROR

        return self._parse_page(html)

    def _parse_page(self, html: str) -> StockStatus:
        if "px-captcha" in html:
            logger.error("Walmart CAPTCHA for %s", self._label)
            return StockStatus.ERROR

        match = NEXT_DATA_RE.search(html)
        if not match:
            logger.error("No __NEXT_DATA__ found for %s", self._label)
            return StockStatus.ERROR

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in __NEXT_DATA__ for %s: %s", self._label, exc)
            return StockStatus.ERROR

        return self._parse_pickup(data)

    def _parse_pickup(self, data: dict) -> StockStatus:
        try:
            product = data["props"]["pageProps"]["initialData"]["data"]["product"]
            fulfillment_options = product["fulfillmentOptions"]
        except (KeyError, TypeError):
            logger.error(
                "Unexpected __NEXT_DATA__ structure for %s: missing product/fulfillment data",
                self._label,
            )
            logger.debug("__NEXT_DATA__ keys: %s", list(data.keys()) if isinstance(data, dict) else type(data))
            return StockStatus.ERROR

        for option in fulfillment_options:
            option_type = option.get("type", "")
            if option_type in ("PICKUP", "IN_STORE"):
                status = option.get("availabilityStatus", "")
                if status == "IN_STOCK":
                    logger.info("Walmart %s: pickup IN_STOCK (type=%s)", self._label, option_type)
                    return StockStatus.IN_STOCK

        logger.info("Walmart %s: pickup OUT_OF_STOCK", self._label)
        return StockStatus.OUT_OF_STOCK

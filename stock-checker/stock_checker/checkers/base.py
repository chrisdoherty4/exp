from enum import Enum
from typing import Protocol


class StockStatus(Enum):
    IN_STOCK = "IN_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"


class Checker(Protocol):
    async def check(self) -> StockStatus: ...

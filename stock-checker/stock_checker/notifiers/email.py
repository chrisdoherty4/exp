import asyncio
import logging
import os
import smtplib
from email.message import EmailMessage

from stock_checker.checkers.base import StockStatus

logger = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(self, recipients: list[str]) -> None:
        self.recipients = recipients
        self.host = os.environ["SMTP_HOST"]
        self.port = int(os.environ.get("SMTP_PORT", "587"))
        self.from_addr = os.environ["SMTP_FROM"]
        self.user = os.environ.get("SMTP_USER", "")
        self.password = os.environ.get("SMTP_PASSWORD", "")

    async def notify(
        self,
        product_key: str,
        product_name: str,
        previous: StockStatus,
        current: StockStatus,
    ) -> None:
        msg = EmailMessage()
        msg["Subject"] = f"Restock Alert: {product_name}"
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.recipients)
        msg.set_content(
            f"{product_name} [{product_key}] is now {current.value} (was {previous.value})."
        )

        logger.info("Sending restock email for %s to %s", product_key, self.recipients)
        await asyncio.to_thread(self._send, msg)
        logger.info("Email sent for %s", product_key)

    def _send(self, msg: EmailMessage) -> None:
        with smtplib.SMTP(self.host, self.port) as server:
            server.starttls()
            if self.user:
                server.login(self.user, self.password)
            server.send_message(msg)

import os
import smtplib
from unittest.mock import MagicMock, patch

import pytest

from stock_checker.checkers.base import StockStatus
from stock_checker.notifiers.email import EmailNotifier

REQUIRED_ENV = {
    "SMTP_HOST": "mail.example.com",
    "SMTP_FROM": "alerts@example.com",
}

FULL_ENV = {
    **REQUIRED_ENV,
    "SMTP_PORT": "465",
    "SMTP_USER": "user@example.com",
    "SMTP_PASSWORD": "secret",
}


class TestEmailNotifierInit:
    @patch.dict(os.environ, REQUIRED_ENV, clear=False)
    def test_required_env_vars(self):
        notifier = EmailNotifier(recipients=["a@b.com"])
        assert notifier.host == "mail.example.com"
        assert notifier.from_addr == "alerts@example.com"
        assert notifier.recipients == ["a@b.com"]

    @patch.dict(os.environ, REQUIRED_ENV, clear=False)
    def test_default_port(self):
        notifier = EmailNotifier(recipients=["a@b.com"])
        assert notifier.port == 587

    @patch.dict(os.environ, FULL_ENV, clear=False)
    def test_custom_port(self):
        notifier = EmailNotifier(recipients=["a@b.com"])
        assert notifier.port == 465

    @patch.dict(os.environ, REQUIRED_ENV, clear=False)
    def test_default_user_and_password(self):
        notifier = EmailNotifier(recipients=["a@b.com"])
        assert notifier.user == ""
        assert notifier.password == ""

    @patch.dict(os.environ, FULL_ENV, clear=False)
    def test_custom_user_and_password(self):
        notifier = EmailNotifier(recipients=["a@b.com"])
        assert notifier.user == "user@example.com"
        assert notifier.password == "secret"

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_smtp_host_raises(self):
        with pytest.raises(KeyError, match="SMTP_HOST"):
            EmailNotifier(recipients=["a@b.com"])

    @patch.dict(os.environ, {"SMTP_HOST": "mail.example.com"}, clear=True)
    def test_missing_smtp_from_raises(self):
        with pytest.raises(KeyError, match="SMTP_FROM"):
            EmailNotifier(recipients=["a@b.com"])


class TestEmailNotifierNotify:
    @patch("stock_checker.notifiers.email.smtplib.SMTP")
    @patch.dict(os.environ, {**FULL_ENV}, clear=False)
    async def test_email_subject_and_body(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        notifier = EmailNotifier(recipients=["a@b.com"])
        await notifier.notify(
            "target:123", "Widget", StockStatus.OUT_OF_STOCK, StockStatus.IN_STOCK
        )

        msg = mock_server.send_message.call_args[0][0]
        assert msg["Subject"] == "Restock Alert: Widget"
        assert msg["From"] == "alerts@example.com"
        assert "a@b.com" in msg["To"]
        assert "Widget [target:123] is now IN_STOCK (was OUT_OF_STOCK)." in msg.get_content()

    @patch("stock_checker.notifiers.email.smtplib.SMTP")
    @patch.dict(os.environ, {**FULL_ENV}, clear=False)
    async def test_multiple_recipients(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        notifier = EmailNotifier(recipients=["a@b.com", "c@d.com"])
        await notifier.notify(
            "target:123", "Widget", StockStatus.OUT_OF_STOCK, StockStatus.IN_STOCK
        )

        msg = mock_server.send_message.call_args[0][0]
        assert "a@b.com" in msg["To"]
        assert "c@d.com" in msg["To"]

    @patch("stock_checker.notifiers.email.smtplib.SMTP")
    @patch.dict(os.environ, {**FULL_ENV}, clear=False)
    async def test_starttls_called(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        notifier = EmailNotifier(recipients=["a@b.com"])
        await notifier.notify(
            "target:123", "Widget", StockStatus.OUT_OF_STOCK, StockStatus.IN_STOCK
        )

        mock_server.starttls.assert_called_once()

    @patch("stock_checker.notifiers.email.smtplib.SMTP")
    @patch.dict(os.environ, {**FULL_ENV}, clear=False)
    async def test_login_called_when_user_set(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        notifier = EmailNotifier(recipients=["a@b.com"])
        await notifier.notify(
            "target:123", "Widget", StockStatus.OUT_OF_STOCK, StockStatus.IN_STOCK
        )

        mock_server.login.assert_called_once_with("user@example.com", "secret")

    @patch("stock_checker.notifiers.email.smtplib.SMTP")
    @patch.dict(os.environ, {**REQUIRED_ENV}, clear=False)
    async def test_login_skipped_when_user_empty(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        notifier = EmailNotifier(recipients=["a@b.com"])
        await notifier.notify(
            "target:123", "Widget", StockStatus.OUT_OF_STOCK, StockStatus.IN_STOCK
        )

        mock_server.login.assert_not_called()

    @patch("stock_checker.notifiers.email.smtplib.SMTP")
    @patch.dict(os.environ, {**REQUIRED_ENV}, clear=False)
    async def test_smtp_connects_with_configured_host_port(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        notifier = EmailNotifier(recipients=["a@b.com"])
        await notifier.notify(
            "target:123", "Widget", StockStatus.OUT_OF_STOCK, StockStatus.IN_STOCK
        )

        mock_smtp_cls.assert_called_once_with("mail.example.com", 587)


class TestEmailNotifierErrors:
    @patch("stock_checker.notifiers.email.smtplib.SMTP")
    @patch.dict(os.environ, {**REQUIRED_ENV}, clear=False)
    async def test_smtp_connection_error_propagates(self, mock_smtp_cls):
        mock_smtp_cls.side_effect = smtplib.SMTPConnectError(421, b"Service not available")

        notifier = EmailNotifier(recipients=["a@b.com"])
        with pytest.raises(smtplib.SMTPConnectError):
            await notifier.notify(
                "target:123", "Widget", StockStatus.OUT_OF_STOCK, StockStatus.IN_STOCK
            )

    @patch("stock_checker.notifiers.email.smtplib.SMTP")
    @patch.dict(os.environ, {**FULL_ENV}, clear=False)
    async def test_smtp_auth_error_propagates(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Bad credentials")

        notifier = EmailNotifier(recipients=["a@b.com"])
        with pytest.raises(smtplib.SMTPAuthenticationError):
            await notifier.notify(
                "target:123", "Widget", StockStatus.OUT_OF_STOCK, StockStatus.IN_STOCK
            )

    @patch("stock_checker.notifiers.email.smtplib.SMTP")
    @patch.dict(os.environ, {**REQUIRED_ENV}, clear=False)
    async def test_send_message_error_propagates(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_server.send_message.side_effect = smtplib.SMTPRecipientsRefused({"a@b.com": (550, b"No such user")})

        notifier = EmailNotifier(recipients=["a@b.com"])
        with pytest.raises(smtplib.SMTPRecipientsRefused):
            await notifier.notify(
                "target:123", "Widget", StockStatus.OUT_OF_STOCK, StockStatus.IN_STOCK
            )

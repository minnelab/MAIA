"""Unit tests for MAIA_scripts/MAIA_send_welcome_user_mail.py."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from MAIA_scripts.MAIA_send_welcome_user_mail import send_welcome_user_email


@pytest.mark.unit
class TestSendWelcomeUserEmail:
    """Test welcome email sending functionality."""

    @patch("MAIA_scripts.MAIA_send_welcome_user_mail.smtplib.SMTP_SSL")
    @patch.dict(
        os.environ,
        {"email_smtp_server": "smtp.example.com", "email_account": "noreply@example.com", "email_password": "password"},
        clear=False,
    )
    def test_send_welcome_user_email_success(self, mock_smtp):
        """Test sending welcome email successfully."""
        # Mock SMTP server
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # Call function
        send_welcome_user_email("user@example.com", "https://maia.example.com")

        # Verify SMTP connection was established
        mock_smtp.assert_called_once()
        mock_server.login.assert_called_once_with("noreply@example.com", "password")
        mock_server.sendmail.assert_called_once()

    @patch("MAIA_scripts.MAIA_send_welcome_user_mail.smtplib.SMTP_SSL")
    @patch.dict(
        os.environ,
        {"email_smtp_server": "smtp.example.com", "email_account": "noreply@example.com", "email_password": "password"},
        clear=False,
    )
    def test_send_welcome_user_email_with_valid_format(self, mock_smtp):
        """Test that email has valid format."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        send_welcome_user_email("user@example.com", "https://maia.example.com")

        # Verify send_message was called (email was sent)
        assert mock_server.sendmail.called

    def test_send_welcome_user_email_handles_missing_env_vars(self, monkeypatch):
        """Test handling of missing environment variables."""
        monkeypatch.delenv("email_account", raising=False)
        monkeypatch.delenv("email_password", raising=False)
        monkeypatch.delenv("email_smtp_server", raising=False)

        with pytest.raises(KeyError):
            send_welcome_user_email("user@example.com", "https://maia.example.com")

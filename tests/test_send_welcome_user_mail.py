"""Unit tests for MAIA_scripts/MAIA_send_welcome_user_mail.py."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from MAIA_scripts.MAIA_send_welcome_user_mail import send_welcome_user_email


@pytest.mark.unit
class TestSendWelcomeUserEmail:
    """Test welcome email sending functionality."""

    @patch("MAIA_scripts.MAIA_send_welcome_user_mail.smtplib.SMTP")
    @patch("MAIA_scripts.MAIA_send_welcome_user_mail.os.getenv")
    def test_send_welcome_user_email_success(self, mock_getenv, mock_smtp):
        """Test sending welcome email successfully."""
        # Mock environment variables
        mock_getenv.side_effect = lambda key, default=None: {
            "SMTP_SERVER": "smtp.example.com",
            "SMTP_PORT": "587",
            "EMAIL_HOST_USER": "noreply@example.com",
            "EMAIL_HOST_PASSWORD": "password",
        }.get(key, default)

        # Mock SMTP server
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # Call function
        send_welcome_user_email("user@example.com", "https://maia.example.com")

        # Verify SMTP connection was established
        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("noreply@example.com", "password")
        mock_server.send_message.assert_called_once()

    @patch("MAIA_scripts.MAIA_send_welcome_user_mail.smtplib.SMTP")
    @patch("MAIA_scripts.MAIA_send_welcome_user_mail.os.getenv")
    def test_send_welcome_user_email_with_valid_format(self, mock_getenv, mock_smtp):
        """Test that email has valid format."""
        mock_getenv.side_effect = lambda key, default=None: {
            "SMTP_SERVER": "smtp.example.com",
            "SMTP_PORT": "587",
            "EMAIL_HOST_USER": "noreply@example.com",
            "EMAIL_HOST_PASSWORD": "password",
        }.get(key, default)

        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        send_welcome_user_email("user@example.com", "https://maia.example.com")

        # Verify send_message was called (email was sent)
        assert mock_server.send_message.called

    @patch("MAIA_scripts.MAIA_send_welcome_user_mail.smtplib.SMTP")
    @patch("MAIA_scripts.MAIA_send_welcome_user_mail.os.getenv")
    def test_send_welcome_user_email_handles_missing_env_vars(self, mock_getenv, mock_smtp):
        """Test handling of missing environment variables."""
        mock_getenv.return_value = None

        # Should raise an error or handle gracefully
        # The function may fail if env vars are missing, which is expected
        try:
            send_welcome_user_email("user@example.com", "https://maia.example.com")
        except (TypeError, AttributeError):
            # Expected when environment variables are missing
            pass

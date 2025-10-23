"""Unit tests for MAIA_scripts/MAIA_send_all_user_email.py."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from MAIA_scripts.MAIA_send_all_user_email import Settings, send_all_users_reminder_email


@pytest.mark.unit
class TestSettings:
    """Test Settings class."""

    def test_settings_init_with_dict(self):
        """Test that Settings object is initialized from dictionary."""
        settings_dict = {"key1": "value1", "key2": "value2", "key3": 123}
        settings = Settings(settings_dict)

        assert hasattr(settings, "key1")
        assert hasattr(settings, "key2")
        assert hasattr(settings, "key3")
        assert settings.key1 == "value1"
        assert settings.key2 == "value2"
        assert settings.key3 == 123

    def test_settings_init_with_empty_dict(self):
        """Test that Settings object handles empty dictionary."""
        settings = Settings({})
        # Should create object without any attributes besides built-ins
        assert isinstance(settings, Settings)


@pytest.mark.unit
class TestSendAllUsersReminderEmail:
    """Test send_all_users_reminder_email function."""

    @patch("MAIA_scripts.MAIA_send_all_user_email.send_maia_message_email")
    @patch("MAIA_scripts.MAIA_send_all_user_email.get_maia_users_from_keycloak")
    @patch("MAIA_scripts.MAIA_send_all_user_email.Path")
    @patch("builtins.open", new_callable=mock_open, read_data="<html>Email content</html>")
    def test_send_all_users_reminder_email_success(
        self, mock_file, mock_path, mock_get_users, mock_send_email, monkeypatch
    ):
        """Test sending reminder email to all users successfully."""
        # Mock environment variables
        monkeypatch.setenv("email_account", "test@example.com")
        monkeypatch.setenv("email_password", "password")
        monkeypatch.setenv("email_smtp_server", "smtp.example.com")

        # Mock Keycloak users
        mock_get_users.return_value = [
            {"email": "user1@example.com"},
            {"email": "user2@example.com"},
        ]

        # Mock successful email send
        mock_send_email.return_value = True

        # Mock path for email template
        mock_path.return_value.parent = Path("/tmp")

        settings_dict = {"OIDC_SERVER_URL": "https://iam.example.com"}

        num_sent, failed = send_all_users_reminder_email(settings_dict)

        assert num_sent == 2
        assert failed == []
        mock_send_email.assert_called_once()

    @patch("MAIA_scripts.MAIA_send_all_user_email.send_maia_message_email")
    @patch("MAIA_scripts.MAIA_send_all_user_email.Path")
    @patch("builtins.open", new_callable=mock_open, read_data="<html>Email content</html>")
    def test_send_all_users_reminder_email_with_custom_list(
        self, mock_file, mock_path, mock_send_email, monkeypatch
    ):
        """Test sending reminder email with custom email list."""
        # Mock environment variables
        monkeypatch.setenv("email_account", "test@example.com")
        monkeypatch.setenv("email_password", "password")
        monkeypatch.setenv("email_smtp_server", "smtp.example.com")

        # Mock successful email send
        mock_send_email.return_value = True

        # Mock path for email template
        mock_path.return_value.parent = Path("/tmp")

        settings_dict = {"OIDC_SERVER_URL": "https://iam.example.com"}
        email_list = ["custom1@example.com", "custom2@example.com", "custom3@example.com"]

        num_sent, failed = send_all_users_reminder_email(settings_dict, email_list)

        assert num_sent == 3
        assert failed == []

    @patch("MAIA_scripts.MAIA_send_all_user_email.send_maia_message_email")
    @patch("MAIA_scripts.MAIA_send_all_user_email.get_maia_users_from_keycloak")
    @patch("MAIA_scripts.MAIA_send_all_user_email.Path")
    @patch("builtins.open", new_callable=mock_open, read_data="<html>Email content</html>")
    def test_send_all_users_reminder_email_failure(
        self, mock_file, mock_path, mock_get_users, mock_send_email, monkeypatch
    ):
        """Test handling of email send failure."""
        # Mock environment variables
        monkeypatch.setenv("email_account", "test@example.com")
        monkeypatch.setenv("email_password", "password")
        monkeypatch.setenv("email_smtp_server", "smtp.example.com")

        # Mock Keycloak users
        mock_get_users.return_value = [
            {"email": "user1@example.com"},
            {"email": "user2@example.com"},
        ]

        # Mock failed email send
        mock_send_email.return_value = False

        # Mock path for email template
        mock_path.return_value.parent = Path("/tmp")

        settings_dict = {"OIDC_SERVER_URL": "https://iam.example.com"}

        num_sent, failed = send_all_users_reminder_email(settings_dict)

        assert num_sent == 0
        assert len(failed) == 2

    def test_send_all_users_reminder_email_missing_env_vars(self):
        """Test that missing environment variables raise an error."""
        settings_dict = {"OIDC_SERVER_URL": "https://iam.example.com"}

        with pytest.raises(EnvironmentError) as exc_info:
            send_all_users_reminder_email(settings_dict)

        assert "Missing required environment variables" in str(exc_info.value)

    @patch("MAIA_scripts.MAIA_send_all_user_email.get_maia_users_from_keycloak")
    @patch("MAIA_scripts.MAIA_send_all_user_email.Path")
    def test_send_all_users_reminder_email_missing_template(
        self, mock_path, mock_get_users, monkeypatch
    ):
        """Test handling of missing email template file."""
        # Mock environment variables
        monkeypatch.setenv("email_account", "test@example.com")
        monkeypatch.setenv("email_password", "password")
        monkeypatch.setenv("email_smtp_server", "smtp.example.com")

        # Mock Keycloak users
        mock_get_users.return_value = [{"email": "user1@example.com"}]

        # Mock path but make file not exist
        mock_path.return_value.parent = Path("/tmp")

        settings_dict = {"OIDC_SERVER_URL": "https://iam.example.com"}

        with patch("builtins.open", side_effect=FileNotFoundError):
            with pytest.raises(FileNotFoundError) as exc_info:
                send_all_users_reminder_email(settings_dict)

            assert "Email template not found" in str(exc_info.value)

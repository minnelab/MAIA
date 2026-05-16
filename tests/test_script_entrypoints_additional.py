"""Additional tests to raise coverage on script helpers and entrypoints."""
from __future__ import annotations

from argparse import Namespace
from unittest.mock import MagicMock, patch

import pytest

from MAIA.maia_k8s_distros import get_gpu_operator_toolkit, get_storage_class
from MAIA_scripts.MAIA_change_keycloak_client_secret import create_admin_user_and_group as change_secret_create_admin
from MAIA_scripts.MAIA_change_keycloak_client_secret import main as change_secret_main
from MAIA_scripts.MAIA_configure_keycloak import create_admin_user_and_group as configure_create_admin
from MAIA_scripts.MAIA_configure_keycloak import create_public_client, main as configure_main
from MAIA_scripts.MAIA_send_all_user_email import get_settings, main as send_all_main
from MAIA_scripts.MAIA_send_welcome_user_mail import main as send_welcome_main


@pytest.mark.unit
class TestKeycloakScriptHelpers:
    @patch("MAIA_scripts.MAIA_change_keycloak_client_secret.KeycloakOpenIDConnection")
    @patch("MAIA_scripts.MAIA_change_keycloak_client_secret.KeycloakAdmin")
    def test_change_secret_create_admin_user_and_group(self, mock_admin_cls, _mock_conn_cls):
        mock_admin = MagicMock()
        mock_admin.get_groups.return_value = [{"id": "g1", "name": "MAIA:user"}]
        mock_admin.get_users.return_value = [{"id": "u1", "email": "admin@maia.se"}]
        mock_admin_cls.return_value = mock_admin

        change_secret_create_admin("https://iam.example.com", "secret")
        mock_admin.create_user.assert_called_once()
        mock_admin.create_group.assert_called_once()
        mock_admin.group_user_add.assert_called_once_with("u1", "g1")

    @patch("MAIA_scripts.MAIA_change_keycloak_client_secret.change_client_secret")
    @patch("MAIA_scripts.MAIA_change_keycloak_client_secret.get_arg_parser")
    def test_change_secret_main_calls_change(self, mock_get_parser, mock_change):
        parser = MagicMock()
        parser.parse_args.return_value = Namespace(client_secret="abc", realm_file="/tmp/realm.json")
        mock_get_parser.return_value = parser

        change_secret_main()
        mock_change.assert_called_once_with("abc", "/tmp/realm.json")

    @patch("MAIA_scripts.MAIA_configure_keycloak.KeycloakOpenIDConnection")
    @patch("MAIA_scripts.MAIA_configure_keycloak.KeycloakAdmin")
    def test_configure_create_public_client(self, mock_admin_cls, _mock_conn_cls):
        mock_admin = MagicMock()
        mock_admin_cls.return_value = mock_admin

        create_public_client("https://iam.example.com", "secret")
        mock_admin.create_client.assert_called_once()

    @patch("MAIA_scripts.MAIA_configure_keycloak.KeycloakOpenIDConnection")
    @patch("MAIA_scripts.MAIA_configure_keycloak.KeycloakAdmin")
    def test_configure_create_admin_user_and_group_client_uuid_missing_raises(self, mock_admin_cls, _mock_conn_cls):
        mock_admin = MagicMock()
        mock_admin.get_groups.return_value = [{"id": "g1", "name": "MAIA:users"}]
        mock_admin.get_users.return_value = [{"id": "u1", "email": "admin@maia.se"}]
        mock_admin.get_client_id.return_value = None
        mock_admin_cls.return_value = mock_admin

        with pytest.raises(ValueError, match="Client UUID not found"):
            configure_create_admin("https://iam.example.com", "secret")

    @patch("MAIA_scripts.MAIA_configure_keycloak.create_admin_user_and_group")
    @patch("MAIA_scripts.MAIA_configure_keycloak.create_public_client")
    @patch("MAIA_scripts.MAIA_configure_keycloak.get_arg_parser")
    def test_configure_main_calls_helpers(self, mock_get_parser, mock_public, mock_admin):
        parser = MagicMock()
        parser.parse_args.return_value = Namespace(
            client_secret="abc",
            server_url="https://iam.example.com",
            admin_email="admin@example.com",
            admin_password="pw",
            admin_group_id="admin",
        )
        mock_get_parser.return_value = parser

        configure_main()
        mock_public.assert_called_once()
        mock_admin.assert_called_once()


@pytest.mark.unit
class TestEmailScriptEntrypoints:
    @patch("MAIA_scripts.MAIA_send_all_user_email.json.load", return_value={"OIDC_SERVER_URL": "https://iam.example.com"})
    @patch("builtins.open")
    def test_send_all_get_settings(self, _mock_open, _mock_load):
        settings = get_settings()
        assert settings["OIDC_SERVER_URL"] == "https://iam.example.com"

    @patch("MAIA_scripts.MAIA_send_all_user_email.send_all_users_reminder_email", return_value=(1, []))
    @patch("MAIA_scripts.MAIA_send_all_user_email.get_settings", return_value={"OIDC_SERVER_URL": "https://iam.example.com"})
    @patch("MAIA_scripts.MAIA_send_all_user_email.get_arg_parser")
    def test_send_all_main_success(self, mock_get_parser, _mock_get_settings, mock_send):
        parser = MagicMock()
        parser.parse_args.return_value = Namespace(email_list="a@b.com")
        mock_get_parser.return_value = parser

        send_all_main()
        mock_send.assert_called_once()

    @patch("MAIA_scripts.MAIA_send_welcome_user_mail.send_welcome_user_email")
    @patch("MAIA_scripts.MAIA_send_welcome_user_mail.get_arg_parser")
    def test_send_welcome_main_success(self, mock_get_parser, mock_send):
        parser = MagicMock()
        parser.parse_args.return_value = Namespace(email="user@example.com", url="https://maia.example.com")
        mock_get_parser.return_value = parser

        send_welcome_main()
        mock_send.assert_called_once_with("user@example.com", "https://maia.example.com")

    @patch("MAIA_scripts.MAIA_send_welcome_user_mail.send_welcome_user_email", side_effect=RuntimeError("boom"))
    @patch("MAIA_scripts.MAIA_send_welcome_user_mail.get_arg_parser")
    def test_send_welcome_main_failure_exits(self, mock_get_parser, _mock_send):
        parser = MagicMock()
        parser.parse_args.return_value = Namespace(email="user@example.com", url="https://maia.example.com")
        mock_get_parser.return_value = parser

        with pytest.raises(SystemExit):
            send_welcome_main()


@pytest.mark.unit
class TestK8sDistrosExtra:
    def test_get_gpu_operator_toolkit_rke2(self):
        toolkit = get_gpu_operator_toolkit("rke2")
        assert toolkit["driver"]["enabled"] is False
        assert any(env["name"] == "CONTAINERD_SOCKET" for env in toolkit["env"])

    def test_get_storage_class_non_dev_distribution(self):
        assert get_storage_class("eks") == "local-path"

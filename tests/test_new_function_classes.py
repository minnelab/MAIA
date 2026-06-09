"""Tests for newer modules/classes/functions added from master."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from MAIA.maia_k8s_distros import get_api_port, get_gpu_operator_toolkit, get_ingress_class, get_storage_class
from MAIA.notifications import (
    confirm_request_registration_for_group,
    confirm_request_registration_to_project,
    send_email_approved_project_registration,
)
from MAIA.versions import define_docker_image_versions, define_maia_admin_versions, define_maia_core_versions
from MAIA_scripts.MAIA_Install import get_arg_parser as get_install_arg_parser
from MAIA_scripts.MAIA_change_keycloak_client_secret import change_client_secret, get_arg_parser as get_change_secret_parser
from MAIA_scripts.MAIA_configure_keycloak import get_arg_parser as get_configure_keycloak_parser
from MAIA_scripts.MAIA_deploy_project import generate_pkce_pair, get_arg_parser as get_deploy_project_parser


@pytest.mark.unit
class TestMaiaK8sDistros:
    def test_get_api_port_known(self):
        assert get_api_port("microk8s") == 16443
        assert get_api_port("k0s") == 6443
        assert get_api_port("k3s") == 6443

    def test_get_api_port_unknown_raises(self, monkeypatch):
        monkeypatch.setenv("K8S_DISTRIBUTION", "unknown")
        with pytest.raises(ValueError):
            get_api_port("unknown")

    def test_get_storage_and_ingress_defaults(self):
        assert get_storage_class("microk8s") == "microk8s-hostpath"
        assert get_storage_class("k3s") == "local-path"
        assert get_ingress_class("k3s") == "maia-core-traefik"
        assert get_ingress_class("eks") == "nginx"

    def test_get_gpu_operator_toolkit_known(self):
        toolkit = get_gpu_operator_toolkit("k0s")
        assert "toolkit" in toolkit
        assert toolkit["operator"]["defaultRuntime"] == "containerd"


@pytest.mark.unit
class TestVersionsModule:
    def test_define_versions_return_dicts(self):
        assert isinstance(define_maia_core_versions(), dict)
        assert isinstance(define_maia_admin_versions(), dict)
        assert isinstance(define_docker_image_versions(), dict)

    def test_define_versions_env_override(self, monkeypatch):
        monkeypatch.setenv("PROMETHEUS_CHART_VERSION", "99.99.99")
        core = define_maia_core_versions()
        assert core["prometheus_chart_version"] == "99.99.99"


@pytest.mark.unit
class TestNotifications:
    @patch("MAIA.notifications.smtplib.SMTP")
    def test_send_email_approved_project_registration(self, mock_smtp):
        send_email_approved_project_registration(
            project_name="project-a",
            project_owner="user@example.com",
            support_link="https://support.example.com",
            dashboard_url="https://dash.example.com/",
            smtp_sender_email="sender@example.com",
            smtp_server="smtp.example.com",
            smtp_port=587,
            smtp_password="pwd",
        )
        assert mock_smtp.called

    @patch("MAIA.notifications.smtplib.SMTP")
    def test_confirmation_helpers_return_true(self, mock_smtp):
        assert (
            confirm_request_registration_to_project(
                "proj",
                "user@example.com",
                "https://support.example.com",
                "https://dash.example.com",
                "sender@example.com",
                "smtp.example.com",
                587,
                "pwd",
            )
            is True
        )
        assert (
            confirm_request_registration_for_group(
                "group",
                "user@example.com",
                "https://support.example.com",
                "https://dash.example.com",
                "sender@example.com",
                "smtp.example.com",
                587,
                "pwd",
            )
            is True
        )


@pytest.mark.unit
class TestNewScriptsParsersAndHelpers:
    def test_maia_install_parser(self):
        parser = get_install_arg_parser()
        args = parser.parse_args(["--config-folder", "/tmp/config"])
        assert args.config_folder == "/tmp/config"

    def test_change_keycloak_client_secret_parser(self):
        parser = get_change_secret_parser()
        args = parser.parse_args(["--client_secret", "abc", "--realm_file", "/tmp/realm.json"])
        assert args.client_secret == "abc"
        assert args.realm_file == "/tmp/realm.json"

    def test_configure_keycloak_parser(self):
        parser = get_configure_keycloak_parser()
        args = parser.parse_args(
            ["--client_secret", "abc", "--server_url", "https://iam", "--admin_email", "admin@example.com"]
        )
        assert args.server_url == "https://iam"
        assert args.admin_email == "admin@example.com"

    def test_deploy_project_parser(self):
        parser = get_deploy_project_parser()
        args = parser.parse_args(["--project-config-file", "/tmp/project.json", "--dashboard-url", "https://dash.example.com"])
        assert args.project_config_file == "/tmp/project.json"
        assert args.dashboard_url == "https://dash.example.com"

    def test_generate_pkce_pair(self):
        verifier, challenge = generate_pkce_pair()
        assert isinstance(verifier, str) and isinstance(challenge, str)
        assert len(verifier) > 10 and len(challenge) > 10

    def test_change_client_secret_updates_realm_file(self, tmp_path):
        realm_file = tmp_path / "realm.json"
        realm_file.write_text(json.dumps({"clients": [{"clientId": "maia", "secret": "old"}, {"clientId": "other"}]}))

        change_client_secret("new-secret", str(realm_file))
        updated = json.loads(realm_file.read_text())
        maia_client = [c for c in updated["clients"] if c["clientId"] == "maia"][0]
        assert maia_client["secret"] == "new-secret"

"""Unit tests for MAIA_scripts/MAIA_deploy_project.py helper functions."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from MAIA_scripts.MAIA_deploy_project import deploy_project, fetch_token, get_token_with_password


@pytest.mark.unit
class TestDeployProjectHelpers:
    """Test token and deployment helper functions."""

    @patch("MAIA_scripts.MAIA_deploy_project.requests.post")
    def test_get_token_with_password(self, mock_post, monkeypatch):
        monkeypatch.setenv("CLIENT_SECRET", "secret")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id_token": "id-token-value"}
        mock_post.return_value = mock_resp

        token = get_token_with_password(
            username="user@example.com",
            password="pwd",
            ca_cert=False,
            token_url="https://iam.example.com/token",
            client_id="maia",
            extra_data={"audience": "dashboard"},
        )

        assert token == "id-token-value"
        sent_data = mock_post.call_args.kwargs["data"]
        assert sent_data["grant_type"] == "password"
        assert sent_data["client_secret"] == "secret"
        assert sent_data["audience"] == "dashboard"

    @patch("MAIA_scripts.MAIA_deploy_project.requests.post")
    def test_fetch_token(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"access_token": "a", "id_token": "b"}
        mock_post.return_value = mock_resp

        tokens = fetch_token(
            auth_code="code123",
            code_verifier="verifier",
            ca_cert=False,
            TOKEN_URL="https://iam.example.com/token",
            CLIENT_ID="maia-public",
            REDIRECT_URI="http://localhost:8080",
        )

        assert tokens["access_token"] == "a"
        assert tokens["id_token"] == "b"
        sent_data = mock_post.call_args.kwargs["data"]
        assert sent_data["grant_type"] == "authorization_code"
        assert sent_data["code"] == "code123"

    @patch("MAIA_scripts.MAIA_deploy_project.requests.post")
    def test_deploy_project_success(self, mock_post, tmp_path):
        project_file = tmp_path / "project.json"
        project_file.write_text(json.dumps({"group_id": "my-group", "foo": "bar"}))

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"values": {"release": "ok"}}
        mock_post.return_value = mock_resp

        result = deploy_project(
            token="jwt",
            dashboard_url="https://dashboard.example.com",
            ca_cert=False,
            project_config_file=str(project_file),
        )

        assert result == {"release": "ok"}
        assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer jwt"

    @patch("MAIA_scripts.MAIA_deploy_project.requests.post")
    def test_deploy_project_failure(self, mock_post, tmp_path):
        project_file = tmp_path / "project.json"
        project_file.write_text(json.dumps({"group_id": "my-group"}))

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "bad request"
        mock_post.return_value = mock_resp

        with pytest.raises(Exception, match="Failed to deploy project: bad request"):
            deploy_project(
                token="jwt",
                dashboard_url="https://dashboard.example.com",
                ca_cert=False,
                project_config_file=str(project_file),
            )

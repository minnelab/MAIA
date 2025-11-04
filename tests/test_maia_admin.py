"""Unit tests for MAIA/maia_admin.py functions."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from MAIA.maia_admin import (
    generate_minio_configs,
    generate_mlflow_configs,
    generate_mysql_configs,
    get_minio_config_if_exists,
    get_mlflow_config_if_exists,
    get_mysql_config_if_exists,
)


@pytest.mark.unit
class TestConfigGenerationFunctions:
    """Test configuration generation functions."""

    def test_generate_minio_configs_returns_dict(self):
        """Test that minio config generation returns a dictionary."""
        result = generate_minio_configs("test-namespace")

        assert isinstance(result, dict)
        assert "console_access_key" in result
        assert "console_secret_key" in result

    def test_generate_minio_configs_has_encoded_credentials(self):
        """Test that minio configs have base64 encoded credentials."""
        import base64

        result = generate_minio_configs("test-namespace")

        # Verify that keys are base64 encoded
        try:
            base64.b64decode(result["console_access_key"])
            base64.b64decode(result["console_secret_key"])
            encoded = True
        except Exception:
            encoded = False

        assert encoded

    def test_generate_mlflow_configs_returns_dict(self):
        """Test that mlflow config generation returns a dictionary."""
        result = generate_mlflow_configs("test-namespace")

        assert isinstance(result, dict)

    def test_generate_mysql_configs_returns_dict(self):
        """Test that mysql config generation returns a dictionary."""
        result = generate_mysql_configs("test-namespace")

        assert isinstance(result, dict)
        assert "mysql_user" in result
        assert "mysql_password" in result

    def test_generate_mysql_configs_has_credentials(self):
        """Test that mysql configs have user and password."""
        result = generate_mysql_configs("test-namespace")

        assert len(result["mysql_user"]) > 0
        assert len(result["mysql_password"]) > 0


@pytest.mark.unit
class TestConfigRetrievalFunctions:
    """Test configuration retrieval functions."""

    @patch("MAIA.maia_admin.Path")
    def test_get_minio_config_if_exists_when_file_exists(self, mock_path):
        """Test retrieving minio config when file exists."""
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_path.return_value.joinpath.return_value = mock_file

        with patch("builtins.open", mock_open(read_data='{"console_access_key": "key", "console_secret_key": "secret"}')):
            result = get_minio_config_if_exists("test-project")

        assert result is not None

    @patch("MAIA.maia_admin.Path")
    def test_get_minio_config_if_exists_when_file_not_exists(self, mock_path):
        """Test retrieving minio config when file doesn't exist."""
        mock_file = MagicMock()
        mock_file.exists.return_value = False
        mock_path.return_value.joinpath.return_value = mock_file

        result = get_minio_config_if_exists("test-project")

        assert result is None

    @patch("MAIA.maia_admin.Path")
    def test_get_mlflow_config_if_exists_when_file_exists(self, mock_path):
        """Test retrieving mlflow config when file exists."""
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_path.return_value.joinpath.return_value = mock_file

        with patch("builtins.open", mock_open(read_data='{"config": "value"}')):
            result = get_mlflow_config_if_exists("test-project")

        assert result is not None

    @patch("MAIA.maia_admin.Path")
    def test_get_mlflow_config_if_exists_when_file_not_exists(self, mock_path):
        """Test retrieving mlflow config when file doesn't exist."""
        mock_file = MagicMock()
        mock_file.exists.return_value = False
        mock_path.return_value.joinpath.return_value = mock_file

        result = get_mlflow_config_if_exists("test-project")

        assert result is None

    @patch("MAIA.maia_admin.Path")
    def test_get_mysql_config_if_exists_when_file_exists(self, mock_path):
        """Test retrieving mysql config when file exists."""
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_path.return_value.joinpath.return_value = mock_file

        with patch("builtins.open", mock_open(read_data='{"mysql_user": "user", "mysql_password": "pass"}')):
            result = get_mysql_config_if_exists("test-project")

        assert result is not None

    @patch("MAIA.maia_admin.Path")
    def test_get_mysql_config_if_exists_when_file_not_exists(self, mock_path):
        """Test retrieving mysql config when file doesn't exist."""
        mock_file = MagicMock()
        mock_file.exists.return_value = False
        mock_path.return_value.joinpath.return_value = mock_file

        result = get_mysql_config_if_exists("test-project")

        assert result is None

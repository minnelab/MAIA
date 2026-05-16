"""Unit tests for MAIA/maia_admin.py functions."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from MAIA.maia_admin import (
    create_harbor_values,
    create_keycloak_values,
    create_maia_admin_toolkit_values,
    create_maia_dashboard_values,
    create_rancher_values,
)


@pytest.mark.unit
class TestMaiaAdminValues:
    """Test MAIA admin values generation helpers."""

    @patch("MAIA.maia_admin.OmegaConf.to_yaml", return_value="x: y")
    def test_create_maia_admin_toolkit_values(self, _mock_to_yaml, temp_config_folder, sample_cluster_config):
        cluster_file = f"{temp_config_folder}/cluster-a.yaml"
        with open(cluster_file, "w") as f:
            f.write("cluster_name: cluster-a\napi: https://cluster-a.example.com\nmaia_dashboard:\n  token: abc\n")
        with patch.dict("os.environ", {"CLUSTER_YAML_CONFIGS": cluster_file}, clear=False):
            result = create_maia_admin_toolkit_values(temp_config_folder, "maia-admin", sample_cluster_config)
        assert isinstance(result, dict)
        assert {"namespace", "release", "repo", "version", "values"}.issubset(result.keys())

    @patch("MAIA.maia_admin.OmegaConf.to_yaml")
    @patch("builtins.open")
    @patch("MAIA.maia_admin.Path")
    def test_create_harbor_values(self, mock_path, _mock_open, _mock_to_yaml, temp_config_folder, sample_cluster_config):
        mock_path.return_value.joinpath.return_value.mkdir = MagicMock()
        result = create_harbor_values(temp_config_folder, "maia-admin", sample_cluster_config)
        assert isinstance(result, dict)
        assert {"namespace", "release", "repo", "version", "values"}.issubset(result.keys())

    @patch("MAIA.maia_admin.OmegaConf.to_yaml")
    @patch("builtins.open")
    @patch("MAIA.maia_admin.Path")
    def test_create_keycloak_values(self, mock_path, _mock_open, _mock_to_yaml, temp_config_folder, sample_cluster_config):
        mock_path.return_value.joinpath.return_value.mkdir = MagicMock()
        result = create_keycloak_values(temp_config_folder, "maia-admin", sample_cluster_config)
        assert isinstance(result, dict)
        assert {"namespace", "release", "repo", "version", "values"}.issubset(result.keys())

    @patch("MAIA.maia_admin.OmegaConf.to_yaml")
    @patch("builtins.open")
    @patch("MAIA.maia_admin.Path")
    @patch("MAIA.maia_admin.generate_human_memorable_password", return_value="safe-password")
    def test_create_maia_dashboard_values(
        self, _mock_password, mock_path, _mock_open, _mock_to_yaml, temp_config_folder, sample_cluster_config
    ):
        mock_path.return_value.joinpath.return_value.mkdir = MagicMock()
        result = create_maia_dashboard_values(temp_config_folder, "maia-admin", sample_cluster_config)
        assert isinstance(result, dict)
        assert {"namespace", "release", "repo", "version", "values"}.issubset(result.keys())

    @patch("MAIA.maia_admin.OmegaConf.to_yaml")
    @patch("builtins.open")
    @patch("MAIA.maia_admin.Path")
    def test_create_rancher_values(self, mock_path, _mock_open, _mock_to_yaml, temp_config_folder, sample_cluster_config):
        mock_path.return_value.joinpath.return_value.mkdir = MagicMock()
        result = create_rancher_values(temp_config_folder, "maia-admin", sample_cluster_config)
        assert isinstance(result, dict)
        assert {"namespace", "release", "repo", "version", "values"}.issubset(result.keys())

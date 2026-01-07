"""Unit tests for MAIA/maia_core.py functions.

Note: Many functions in maia_core.py create complex Helm values configurations
and require extensive mocking of Kubernetes APIs. These tests focus on verifying
that the functions execute and return properly structured data.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestPrometheusValues:
    """Test Prometheus values creation."""

    @patch("MAIA.maia_core.config.load_kube_config")
    @patch("MAIA.maia_core.client.CoreV1Api")
    def test_create_prometheus_values_structure(
        self, mock_core_api, mock_load_config, temp_config_folder, sample_cluster_config, sample_maia_config
    ):
        """Test that prometheus values have proper structure."""
        from MAIA.maia_core import create_prometheus_values

        # Mock Kubernetes API
        mock_v1 = MagicMock()
        mock_core_api.return_value = mock_v1

        # Mock nodes response
        mock_node = MagicMock()
        mock_address = MagicMock()
        mock_address.type = "InternalIP"
        mock_address.address = "192.168.1.1"
        mock_node.status.addresses = [mock_address]

        mock_nodes = MagicMock()
        mock_nodes.items = [mock_node]
        mock_v1.list_node.return_value = mock_nodes

        result = create_prometheus_values(
            temp_config_folder, "test-project", sample_cluster_config, sample_maia_config
        )

        assert isinstance(result, dict)
        assert "namespace" in result
        assert "chart_name" in result
        assert "repo_url" in result


@pytest.mark.unit
class TestLokiValues:
    """Test Loki values creation."""

    @patch("MAIA.maia_core.OmegaConf.to_yaml")
    @patch("builtins.open")
    @patch("MAIA.maia_core.Path")
    def test_create_loki_values_creates_config(self, mock_path, mock_open, mock_to_yaml, temp_config_folder):
        """Test that Loki values config is created."""
        from MAIA.maia_core import create_loki_values

        # Setup mocks
        mock_path.return_value.joinpath.return_value.mkdir = MagicMock()
        mock_to_yaml.return_value = "test: config"

        result = create_loki_values(temp_config_folder, "test-project")

        assert isinstance(result, dict)
        assert "namespace" in result
        assert "chart_name" in result


@pytest.mark.unit
class TestTempoValues:
    """Test Tempo values creation."""

    @patch("MAIA.maia_core.OmegaConf.to_yaml")
    @patch("builtins.open")
    @patch("MAIA.maia_core.Path")
    def test_create_tempo_values_creates_config(self, mock_path, mock_open, mock_to_yaml, temp_config_folder):
        """Test that Tempo values config is created."""
        from MAIA.maia_core import create_tempo_values

        # Setup mocks
        mock_path.return_value.joinpath.return_value.mkdir = MagicMock()
        mock_to_yaml.return_value = "test: config"

        result = create_tempo_values(temp_config_folder, "test-project")

        assert isinstance(result, dict)
        assert "namespace" in result
        assert "chart_name" in result


@pytest.mark.unit
class TestCoreToolkitValues:
    """Test core toolkit values creation."""

    @patch("MAIA.maia_core.OmegaConf.to_yaml")
    @patch("builtins.open")
    @patch("MAIA.maia_core.Path")
    def test_create_core_toolkit_values(
        self, mock_path, mock_open, mock_to_yaml, temp_config_folder, sample_cluster_config
    ):
        """Test that core toolkit values are created."""
        from MAIA.maia_core import create_core_toolkit_values

        # Setup mocks
        mock_path.return_value.joinpath.return_value.mkdir = MagicMock()
        mock_to_yaml.return_value = "test: config"

        result = create_core_toolkit_values(temp_config_folder, "test-project", sample_cluster_config)

        assert isinstance(result, dict)


@pytest.mark.unit
class TestTraefikValues:
    """Test Traefik values creation."""

    @patch("MAIA.maia_core.OmegaConf.to_yaml")
    @patch("builtins.open")
    @patch("MAIA.maia_core.Path")
    def test_create_traefik_values(
        self, mock_path, mock_open, mock_to_yaml, temp_config_folder, sample_cluster_config
    ):
        """Test that Traefik values are created."""
        from MAIA.maia_core import create_traefik_values

        # Setup mocks
        mock_path.return_value.joinpath.return_value.mkdir = MagicMock()
        mock_to_yaml.return_value = "test: config"

        result = create_traefik_values(temp_config_folder, "test-project", sample_cluster_config)

        assert isinstance(result, dict)
        assert "namespace" in result
        assert "chart_name" in result


@pytest.mark.unit
class TestMetalLBValues:
    """Test MetalLB values creation."""

    @patch("MAIA.maia_core.OmegaConf.to_yaml")
    @patch("builtins.open")
    @patch("MAIA.maia_core.Path")
    def test_create_metallb_values(self, mock_path, mock_open, mock_to_yaml, temp_config_folder):
        """Test that MetalLB values are created."""
        from MAIA.maia_core import create_metallb_values

        # Setup mocks
        mock_path.return_value.joinpath.return_value.mkdir = MagicMock()
        mock_to_yaml.return_value = "test: config"

        result = create_metallb_values(temp_config_folder, "test-project")

        assert isinstance(result, dict)


@pytest.mark.unit
class TestCertManagerValues:
    """Test cert-manager values creation."""

    @patch("MAIA.maia_core.OmegaConf.to_yaml")
    @patch("builtins.open")
    @patch("MAIA.maia_core.Path")
    def test_create_cert_manager_values(self, mock_path, mock_open, mock_to_yaml, temp_config_folder):
        """Test that cert-manager values are created."""
        from MAIA.maia_core import create_cert_manager_values

        # Setup mocks
        mock_path.return_value.joinpath.return_value.mkdir = MagicMock()
        mock_to_yaml.return_value = "test: config"

        result = create_cert_manager_values(temp_config_folder, "test-project")

        assert isinstance(result, dict)


@pytest.mark.unit
class TestIngressNginxValues:
    """Test ingress-nginx values creation."""

    @patch("MAIA.maia_core.OmegaConf.to_yaml")
    @patch("builtins.open")
    @patch("MAIA.maia_core.Path")
    def test_create_ingress_nginx_values(self, mock_path, mock_open, mock_to_yaml, temp_config_folder):
        """Test that ingress-nginx values are created."""
        from MAIA.maia_core import create_ingress_nginx_values

        # Setup mocks
        mock_path.return_value.joinpath.return_value.mkdir = MagicMock()
        mock_to_yaml.return_value = "test: config"

        result = create_ingress_nginx_values(temp_config_folder, "test-project")

        assert isinstance(result, dict)

"""Unit tests for MAIA/helm_values.py functions."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from MAIA.helm_values import read_config_dict_and_generate_helm_values_dict


@pytest.mark.unit
class TestHelmValues:
    """Test Helm values generation functions."""

    @patch("MAIA.helm_values.config.load_kube_config_from_dict")
    def test_read_config_dict_basic_structure(self, mock_load_config, sample_kubeconfig):
        """Test that basic config dict generates valid helm values."""
        config_dict = {
            "namespace": "test-namespace",
            "chart_name": "test-chart",
            "docker_image": "test-image",
            "tag": "1.0.0",
        }

        result = read_config_dict_and_generate_helm_values_dict(config_dict, sample_kubeconfig)

        assert isinstance(result, dict)
        assert "namespace" in result or "chart_name" in result

    @patch("MAIA.helm_values.config.load_kube_config_from_dict")
    def test_read_config_dict_with_deployment(self, mock_load_config, sample_kubeconfig):
        """Test config dict with deployment settings."""
        config_dict = {
            "namespace": "test-namespace",
            "chart_name": "test-chart",
            "docker_image": "test-image",
            "tag": "1.0.0",
            "deployment": True,
            "memory_request": "2Gi",
            "cpu_request": "500m",
        }

        result = read_config_dict_and_generate_helm_values_dict(config_dict, sample_kubeconfig)

        assert isinstance(result, dict)

    @patch("MAIA.helm_values.config.load_kube_config_from_dict")
    def test_read_config_dict_with_ports(self, mock_load_config, sample_kubeconfig):
        """Test config dict with port configuration."""
        config_dict = {
            "namespace": "test-namespace",
            "chart_name": "test-chart",
            "docker_image": "test-image",
            "tag": "1.0.0",
            "ports": {"http": [8080], "https": [8443]},
        }

        result = read_config_dict_and_generate_helm_values_dict(config_dict, sample_kubeconfig)

        assert isinstance(result, dict)

    @patch("MAIA.helm_values.config.load_kube_config_from_dict")
    def test_read_config_dict_with_persistent_volume(self, mock_load_config, sample_kubeconfig):
        """Test config dict with persistent volume configuration."""
        config_dict = {
            "namespace": "test-namespace",
            "chart_name": "test-chart",
            "docker_image": "test-image",
            "tag": "1.0.0",
            "persistent_volume": [
                {
                    "mountPath": "/data",
                    "size": "10Gi",
                    "access_mode": "ReadWriteOnce",
                    "pvc_type": "standard",
                }
            ],
        }

        result = read_config_dict_and_generate_helm_values_dict(config_dict, sample_kubeconfig)

        assert isinstance(result, dict)

    @patch("MAIA.helm_values.config.load_kube_config_from_dict")
    def test_read_config_dict_with_env_variables(self, mock_load_config, sample_kubeconfig):
        """Test config dict with environment variables."""
        config_dict = {
            "namespace": "test-namespace",
            "chart_name": "test-chart",
            "docker_image": "test-image",
            "tag": "1.0.0",
            "env_variables": {"VAR1": "value1", "VAR2": "value2"},
        }

        result = read_config_dict_and_generate_helm_values_dict(config_dict, sample_kubeconfig)

        assert isinstance(result, dict)

    @patch("MAIA.helm_values.config.load_kube_config_from_dict")
    def test_read_config_dict_with_ingress(self, mock_load_config, sample_kubeconfig):
        """Test config dict with ingress configuration."""
        config_dict = {
            "namespace": "test-namespace",
            "chart_name": "test-chart",
            "docker_image": "test-image",
            "tag": "1.0.0",
            "ingress": {
                "enabled": True,
                "path": "/app",
                "host": "app.example.com",
                "port": 80,
                "annotations": {"cert-manager.io/cluster-issuer": "letsencrypt"},
            },
        }

        result = read_config_dict_and_generate_helm_values_dict(config_dict, sample_kubeconfig)

        assert isinstance(result, dict)

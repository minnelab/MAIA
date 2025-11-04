"""Additional unit tests for MAIA/maia_fn.py deployment functions."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from MAIA.maia_fn import deploy_mlflow, deploy_mysql, deploy_oauth2_proxy, deploy_orthanc, gpu_list_from_nodes


@pytest.mark.unit
class TestDeployOAuth2Proxy:
    """Test OAuth2 Proxy deployment function."""

    @patch("MAIA.maia_fn.OmegaConf.to_yaml")
    @patch("builtins.open")
    @patch("MAIA.maia_fn.Path")
    def test_deploy_oauth2_proxy_subdomain(
        self, mock_path, mock_open, mock_to_yaml, temp_config_folder, sample_cluster_config, sample_user_config
    ):
        """Test OAuth2 proxy deployment with subdomain URL type."""
        sample_cluster_config["url_type"] = "subdomain"

        # Mock path operations
        mock_path.return_value.joinpath.return_value.mkdir = MagicMock()

        result = deploy_oauth2_proxy(sample_cluster_config, sample_user_config, temp_config_folder)

        assert isinstance(result, dict)
        assert "namespace" in result
        assert "release" in result
        assert "chart" in result
        assert "repo" in result
        assert "version" in result
        assert "values" in result

    @patch("MAIA.maia_fn.OmegaConf.to_yaml")
    @patch("builtins.open")
    @patch("MAIA.maia_fn.Path")
    def test_deploy_oauth2_proxy_subpath(
        self, mock_path, mock_open, mock_to_yaml, temp_config_folder, sample_cluster_config, sample_user_config
    ):
        """Test OAuth2 proxy deployment with subpath URL type."""
        sample_cluster_config["url_type"] = "subpath"

        # Mock path operations
        mock_path.return_value.joinpath.return_value.mkdir = MagicMock()

        result = deploy_oauth2_proxy(sample_cluster_config, sample_user_config, temp_config_folder)

        assert isinstance(result, dict)
        assert "namespace" in result


@pytest.mark.unit
class TestDeployMySQL:
    """Test MySQL deployment function."""

    @patch("MAIA.maia_fn.OmegaConf.to_yaml")
    @patch("builtins.open")
    @patch("MAIA.maia_fn.Path")
    @patch("MAIA.maia_fn.yaml.safe_load")
    @patch("MAIA.maia_fn.read_config_dict_and_generate_helm_values_dict")
    def test_deploy_mysql_basic(
        self,
        mock_helm_values,
        mock_yaml,
        mock_path,
        mock_open,
        mock_to_yaml,
        temp_config_folder,
        sample_cluster_config,
        sample_user_config,
        sample_kubeconfig,
        monkeypatch,
    ):
        """Test basic MySQL deployment."""
        # Setup mocks
        mock_yaml.return_value = sample_kubeconfig
        mock_helm_values.return_value = {"chart_name": "mkg", "namespace": "test"}
        mock_path.return_value.read_text.return_value = "test: config"
        mock_path.return_value.joinpath.return_value.mkdir = MagicMock()

        mysql_configs = {"mysql_user": "testuser", "mysql_password": "testpass"}

        result = deploy_mysql(sample_cluster_config, sample_user_config, temp_config_folder, mysql_configs)

        assert isinstance(result, dict)
        assert "namespace" in result
        assert "release" in result
        assert "chart" in result


@pytest.mark.unit
class TestDeployMLflow:
    """Test MLflow deployment function."""

    @patch("MAIA.maia_fn.OmegaConf.to_yaml")
    @patch("builtins.open")
    @patch("MAIA.maia_fn.Path")
    @patch("MAIA.maia_fn.yaml.safe_load")
    @patch("MAIA.maia_fn.config.load_kube_config_from_dict")
    @patch("MAIA.maia_fn.read_config_dict_and_generate_helm_values_dict")
    def test_deploy_mlflow_basic(
        self,
        mock_helm_values,
        mock_load_config,
        mock_yaml,
        mock_path,
        mock_open,
        mock_to_yaml,
        temp_config_folder,
        sample_cluster_config,
        sample_user_config,
        sample_maia_config,
        sample_kubeconfig,
    ):
        """Test basic MLflow deployment."""
        # Setup mocks
        mock_yaml.return_value = sample_kubeconfig
        mock_helm_values.return_value = {"chart_name": "mkg", "namespace": "test"}
        mock_path.return_value.read_text.return_value = "test: config"
        mock_path.return_value.joinpath.return_value.mkdir = MagicMock()

        mysql_config = {"mysql_user": "testuser", "mysql_password": "testpass"}
        minio_config = {"console_access_key": "bWluaW8=", "console_secret_key": "bWluaW8xMjM="}

        result = deploy_mlflow(
            sample_cluster_config, sample_user_config, temp_config_folder, sample_maia_config, mysql_config, minio_config
        )

        assert isinstance(result, dict)
        assert "namespace" in result
        assert "release" in result


@pytest.mark.unit
class TestDeployOrthanc:
    """Test Orthanc deployment function."""

    @patch("MAIA.maia_fn.OmegaConf.to_yaml")
    @patch("builtins.open")
    @patch("MAIA.maia_fn.Path")
    def test_deploy_orthanc_basic(
        self,
        mock_path,
        mock_open_func,
        mock_to_yaml,
        temp_config_folder,
        sample_cluster_config,
        sample_user_config,
        sample_maia_config,
    ):
        """Test basic Orthanc deployment."""
        # Create mock namespace values file
        mock_file = MagicMock()
        mock_path.return_value.joinpath.return_value = temp_config_folder

        # Create the directory structure
        namespace_values_path = Path(temp_config_folder) / sample_user_config["group_ID"] / "maia_namespace_values"
        namespace_values_path.mkdir(parents=True, exist_ok=True)

        # Create namespace_values.yaml
        import yaml

        with open(namespace_values_path / "namespace_values.yaml", "w") as f:
            yaml.dump({"orthanc": {"port": 8042}}, f)

        result = deploy_orthanc(sample_cluster_config, sample_user_config, sample_maia_config, temp_config_folder)

        assert isinstance(result, dict)
        assert "namespace" in result
        assert "release" in result
        assert "chart" in result


@pytest.mark.unit
class TestGPUListFromNodes:
    """Test GPU listing function."""

    @patch("MAIA.maia_fn.yaml.safe_load")
    @patch("MAIA.maia_fn.Path")
    @patch("MAIA.maia_fn.config.load_kube_config_from_dict")
    @patch("MAIA.maia_fn.client.CoreV1Api")
    def test_gpu_list_from_nodes_with_gpus(self, mock_core_api, mock_load_config, mock_path, mock_yaml):
        """Test getting GPU list from nodes with GPUs."""
        # Mock kubeconfig
        mock_yaml.return_value = {"test": "config"}
        mock_path.return_value.read_text.return_value = "test: config"

        # Mock Kubernetes API
        mock_v1 = MagicMock()
        mock_core_api.return_value = mock_v1

        # Create mock node with GPU
        mock_node = MagicMock()
        mock_node.metadata.name = "gpu-node-1"
        mock_node.metadata.labels = {
            "nvidia.com/gpu.product": "NVIDIA-GeForce-RTX-3090",
            "nvidia.com/gpu.count": "2",
        }

        # Create mock condition
        mock_condition = MagicMock()
        mock_condition.type = "Ready"
        mock_condition.status = "True"
        mock_node.status.conditions = [mock_condition]

        mock_nodes = MagicMock()
        mock_nodes.items = [mock_node]
        mock_v1.list_node.return_value = mock_nodes

        result = gpu_list_from_nodes()

        assert isinstance(result, dict)
        assert "gpu-node-1" in result
        assert result["gpu-node-1"][0] == "NVIDIA-GeForce-RTX-3090"
        assert result["gpu-node-1"][1] == "2"

    @patch("MAIA.maia_fn.yaml.safe_load")
    @patch("MAIA.maia_fn.Path")
    @patch("MAIA.maia_fn.config.load_kube_config_from_dict")
    @patch("MAIA.maia_fn.client.CoreV1Api")
    def test_gpu_list_from_nodes_without_gpus(self, mock_core_api, mock_load_config, mock_path, mock_yaml):
        """Test getting GPU list from nodes without GPUs."""
        # Mock kubeconfig
        mock_yaml.return_value = {"test": "config"}
        mock_path.return_value.read_text.return_value = "test: config"

        # Mock Kubernetes API
        mock_v1 = MagicMock()
        mock_core_api.return_value = mock_v1

        # Create mock node without GPU labels
        mock_node = MagicMock()
        mock_node.metadata.name = "cpu-node-1"
        mock_node.metadata.labels = {}

        # Create mock condition
        mock_condition = MagicMock()
        mock_condition.type = "Ready"
        mock_condition.status = "True"
        mock_node.status.conditions = [mock_condition]

        mock_nodes = MagicMock()
        mock_nodes.items = [mock_node]
        mock_v1.list_node.return_value = mock_nodes

        result = gpu_list_from_nodes()

        assert isinstance(result, dict)
        assert "cpu-node-1" not in result  # Node without GPU should not be in result

    @patch("MAIA.maia_fn.yaml.safe_load")
    @patch("MAIA.maia_fn.Path")
    @patch("MAIA.maia_fn.config.load_kube_config_from_dict")
    @patch("MAIA.maia_fn.client.CoreV1Api")
    def test_gpu_list_from_nodes_not_ready(self, mock_core_api, mock_load_config, mock_path, mock_yaml):
        """Test that not-ready nodes are excluded."""
        # Mock kubeconfig
        mock_yaml.return_value = {"test": "config"}
        mock_path.return_value.read_text.return_value = "test: config"

        # Mock Kubernetes API
        mock_v1 = MagicMock()
        mock_core_api.return_value = mock_v1

        # Create mock node with GPU but not ready
        mock_node = MagicMock()
        mock_node.metadata.name = "gpu-node-1"
        mock_node.metadata.labels = {
            "nvidia.com/gpu.product": "NVIDIA-GeForce-RTX-3090",
            "nvidia.com/gpu.count": "2",
        }

        # Create mock condition (not ready)
        mock_condition = MagicMock()
        mock_condition.type = "Ready"
        mock_condition.status = "False"
        mock_node.status.conditions = [mock_condition]

        mock_nodes = MagicMock()
        mock_nodes.items = [mock_node]
        mock_v1.list_node.return_value = mock_nodes

        result = gpu_list_from_nodes()

        assert isinstance(result, dict)
        assert "gpu-node-1" not in result  # Not-ready node should not be in result

"""Unit tests for MAIA/kubernetes_utils.py functions."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from MAIA.kubernetes_utils import (
    create_namespace_from_context,
    get_filtered_available_nodes,
    label_pod_for_deletion,
)


@pytest.mark.unit
class TestKubernetesUtils:
    """Test Kubernetes utility functions."""

    def test_get_filtered_available_nodes_all_matching(self):
        """Test filtering nodes when all nodes match requirements."""
        gpu_dict = {"node1": [2], "node2": [2]}
        cpu_dict = {"node1": [16], "node2": [16]}
        ram_dict = {"node1": [64], "node2": [64]}

        gpu_res, cpu_res, ram_res = get_filtered_available_nodes(
            gpu_dict, cpu_dict, ram_dict, gpu_request=1, cpu_request=8, memory_request=32
        )

        assert len(gpu_res) == 2
        assert len(cpu_res) == 2
        assert len(ram_res) == 2

    def test_get_filtered_available_nodes_partial_match(self):
        """Test filtering nodes when only some nodes match requirements."""
        gpu_dict = {"node1": [2], "node2": [0], "node3": [2]}
        cpu_dict = {"node1": [16], "node2": [8], "node3": [16]}
        ram_dict = {"node1": [64], "node2": [32], "node3": [64]}

        gpu_res, _, _ = get_filtered_available_nodes(
            gpu_dict, cpu_dict, ram_dict, gpu_request=1, cpu_request=8, memory_request=32
        )

        assert set(gpu_res.keys()) == {"node1", "node3"}

    def test_get_filtered_available_nodes_insufficient_cpu(self):
        """Test filtering nodes when CPU requirements aren't met."""
        gpu_dict = {"node1": [2]}
        cpu_dict = {"node1": [4]}
        ram_dict = {"node1": [64]}

        gpu_res, _, _ = get_filtered_available_nodes(
            gpu_dict, cpu_dict, ram_dict, gpu_request=1, cpu_request=8, memory_request=32
        )

        assert gpu_res == {}

    def test_get_filtered_available_nodes_insufficient_memory(self):
        """Test filtering nodes when memory requirements aren't met."""
        gpu_dict = {"node1": [2]}
        cpu_dict = {"node1": [16]}
        ram_dict = {"node1": [16]}

        gpu_res, _, _ = get_filtered_available_nodes(
            gpu_dict, cpu_dict, ram_dict, gpu_request=1, cpu_request=8, memory_request=32
        )

        assert gpu_res == {}

    def test_get_filtered_available_nodes_wrong_gpu_type(self):
        """Test filtering nodes when GPU type doesn't match."""
        gpu_dict = {"node1": [0]}
        cpu_dict = {"node1": [16]}
        ram_dict = {"node1": [64]}

        gpu_res, _, _ = get_filtered_available_nodes(
            gpu_dict, cpu_dict, ram_dict, gpu_request=1, cpu_request=8, memory_request=32
        )

        assert gpu_res == {}

    def test_get_filtered_available_nodes_empty_input(self):
        """Test filtering with empty node dictionaries."""
        result = get_filtered_available_nodes({}, {}, {}, gpu_request=1, cpu_request=8, memory_request=32)

        assert isinstance(result, tuple)
        assert result == ({}, {}, {})

    @patch("MAIA.kubernetes_utils.config.load_kube_config")
    @patch("MAIA.kubernetes_utils.client.CoreV1Api")
    def test_label_pod_for_deletion(self, mock_core_api, mock_load_config):
        """Test labeling a pod for deletion."""
        mock_v1 = MagicMock()
        mock_core_api.return_value = mock_v1

        label_pod_for_deletion("test-namespace", "test-pod")

        # Verify patch_namespaced_pod was called
        mock_v1.patch_namespaced_pod.assert_called_once()

    @patch("MAIA.kubernetes_utils.kubernetes.client.ApiClient")
    @patch("MAIA.kubernetes_utils.kubernetes.client.CoreV1Api")
    def test_create_namespace_from_context(self, mock_core_api, mock_api_client):
        """Test creating a namespace from context."""
        from kubernetes.client.exceptions import ApiException

        mock_v1 = MagicMock()
        mock_core_api.return_value = mock_v1
        mock_v1.read_namespace.side_effect = ApiException(status=404)
        mock_api_client.return_value.__enter__.return_value = MagicMock()

        create_namespace_from_context("test-namespace")

        assert mock_v1.create_namespace.called or mock_v1.read_namespace.called

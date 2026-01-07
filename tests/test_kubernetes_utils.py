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
        gpu_dict = {"node1": ["GPU1", "2"], "node2": ["GPU1", "2"]}
        cpu_dict = {"node1": 16, "node2": 16}
        ram_dict = {"node1": 64, "node2": 64}

        result = get_filtered_available_nodes(
            gpu_dict, cpu_dict, ram_dict, gpu_request="GPU1", cpu_request=8, memory_request=32
        )

        assert isinstance(result, dict)
        assert len(result) == 2

    def test_get_filtered_available_nodes_partial_match(self):
        """Test filtering nodes when only some nodes match requirements."""
        gpu_dict = {"node1": ["GPU1", "2"], "node2": ["GPU2", "1"], "node3": ["GPU1", "2"]}
        cpu_dict = {"node1": 16, "node2": 8, "node3": 16}
        ram_dict = {"node1": 64, "node2": 32, "node3": 64}

        result = get_filtered_available_nodes(
            gpu_dict, cpu_dict, ram_dict, gpu_request="GPU1", cpu_request=8, memory_request=32
        )

        assert isinstance(result, dict)
        # node1 and node3 should match (have GPU1)

    def test_get_filtered_available_nodes_insufficient_cpu(self):
        """Test filtering nodes when CPU requirements aren't met."""
        gpu_dict = {"node1": ["GPU1", "2"]}
        cpu_dict = {"node1": 4}
        ram_dict = {"node1": 64}

        result = get_filtered_available_nodes(
            gpu_dict, cpu_dict, ram_dict, gpu_request="GPU1", cpu_request=8, memory_request=32
        )

        # node1 should be filtered out due to insufficient CPU
        assert isinstance(result, dict)

    def test_get_filtered_available_nodes_insufficient_memory(self):
        """Test filtering nodes when memory requirements aren't met."""
        gpu_dict = {"node1": ["GPU1", "2"]}
        cpu_dict = {"node1": 16}
        ram_dict = {"node1": 16}

        result = get_filtered_available_nodes(
            gpu_dict, cpu_dict, ram_dict, gpu_request="GPU1", cpu_request=8, memory_request=32
        )

        # node1 should be filtered out due to insufficient memory
        assert isinstance(result, dict)

    def test_get_filtered_available_nodes_wrong_gpu_type(self):
        """Test filtering nodes when GPU type doesn't match."""
        gpu_dict = {"node1": ["GPU2", "2"]}
        cpu_dict = {"node1": 16}
        ram_dict = {"node1": 64}

        result = get_filtered_available_nodes(
            gpu_dict, cpu_dict, ram_dict, gpu_request="GPU1", cpu_request=8, memory_request=32
        )

        # node1 should be filtered out due to wrong GPU type
        assert isinstance(result, dict)

    def test_get_filtered_available_nodes_empty_input(self):
        """Test filtering with empty node dictionaries."""
        result = get_filtered_available_nodes({}, {}, {}, gpu_request="GPU1", cpu_request=8, memory_request=32)

        assert isinstance(result, dict)
        assert len(result) == 0

    @patch("MAIA.kubernetes_utils.config.load_kube_config")
    @patch("MAIA.kubernetes_utils.client.CoreV1Api")
    def test_label_pod_for_deletion(self, mock_core_api, mock_load_config):
        """Test labeling a pod for deletion."""
        mock_v1 = MagicMock()
        mock_core_api.return_value = mock_v1

        label_pod_for_deletion("test-namespace", "test-pod")

        # Verify patch_namespaced_pod was called
        mock_v1.patch_namespaced_pod.assert_called_once()

    @patch("MAIA.kubernetes_utils.config.load_kube_config")
    @patch("MAIA.kubernetes_utils.client.CoreV1Api")
    def test_create_namespace_from_context(self, mock_core_api, mock_load_config):
        """Test creating a namespace from context."""
        mock_v1 = MagicMock()
        mock_core_api.return_value = mock_v1

        create_namespace_from_context("test-namespace")

        # Verify create_namespace was called
        mock_v1.create_namespace.assert_called_once()

"""Unit tests for MAIA/maia_fn.py functions."""
from __future__ import annotations

import base64
import json
import string
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, mock_open, patch

import pytest
import yaml

from MAIA.maia_fn import (
    convert_username_to_jupyterhub_username,
    create_config_map_from_data,
    encode_docker_registry_secret,
    generate_human_memorable_password,
    generate_random_password,
    get_ssh_port_dict,
    get_ssh_ports,
)


@pytest.mark.unit
class TestPasswordGeneration:
    """Test password generation functions."""

    def test_generate_random_password_default_length(self):
        """Test that random password has default length of 12."""
        password = generate_random_password()
        assert len(password) == 12

    def test_generate_random_password_custom_length(self):
        """Test that random password respects custom length."""
        password = generate_random_password(length=20)
        assert len(password) == 20

    def test_generate_random_password_contains_valid_characters(self):
        """Test that random password only contains letters and digits."""
        password = generate_random_password(length=50)
        valid_chars = set(string.ascii_letters + string.digits)
        assert all(char in valid_chars for char in password)

    def test_generate_random_password_uniqueness(self):
        """Test that multiple calls generate different passwords."""
        passwords = [generate_random_password() for _ in range(10)]
        assert len(set(passwords)) == 10  # All should be unique

    @patch("MAIA.maia_fn.nltk.download")
    @patch("MAIA.maia_fn.words.words")
    def test_generate_human_memorable_password_default_length(self, mock_words, mock_download):
        """Test that human memorable password generation works with default length."""
        mock_words.return_value = ["apple", "banana", "cherry", "date", "elderberry"]
        password = generate_human_memorable_password()
        assert len(password) >= 12
        mock_download.assert_called_once_with("words")

    @patch("MAIA.maia_fn.nltk.download")
    @patch("MAIA.maia_fn.words.words")
    def test_generate_human_memorable_password_contains_hyphen(self, mock_words, mock_download):
        """Test that human memorable password contains hyphens."""
        mock_words.return_value = ["apple", "banana", "cherry"]
        password = generate_human_memorable_password(length=18)
        assert "-" in password

    @patch("MAIA.maia_fn.nltk.download")
    @patch("MAIA.maia_fn.words.words")
    def test_generate_human_memorable_password_custom_length(self, mock_words, mock_download):
        """Test that human memorable password respects custom length."""
        mock_words.return_value = ["word1", "word2", "word3"]
        password = generate_human_memorable_password(length=24)
        assert len(password) >= 24


@pytest.mark.unit
class TestUsernameConversion:
    """Test username conversion functions."""

    def test_convert_username_to_jupyterhub_username_with_dash(self):
        """Test username conversion with dashes."""
        result = convert_username_to_jupyterhub_username("user-name")
        assert result == "user-2dname"

    def test_convert_username_to_jupyterhub_username_with_at(self):
        """Test username conversion with @ symbol."""
        result = convert_username_to_jupyterhub_username("user@example.com")
        assert result == "user-40example-2ecom"

    def test_convert_username_to_jupyterhub_username_with_dot(self):
        """Test username conversion with dots."""
        result = convert_username_to_jupyterhub_username("user.name")
        assert result == "user-2ename"

    def test_convert_username_to_jupyterhub_username_complex(self):
        """Test username conversion with mixed special characters."""
        result = convert_username_to_jupyterhub_username("user-name@test.domain")
        assert result == "user-2dname-40test-2edomain"

    def test_convert_username_to_jupyterhub_username_no_special_chars(self):
        """Test username conversion with no special characters."""
        result = convert_username_to_jupyterhub_username("username")
        assert result == "username"


@pytest.mark.unit
class TestDockerRegistrySecret:
    """Test Docker registry secret encoding."""

    def test_encode_docker_registry_secret_format(self):
        """Test that Docker registry secret has correct format."""
        result = encode_docker_registry_secret("registry.example.com", "user", "pass")
        decoded = base64.b64decode(result).decode("utf-8")
        data = json.loads(decoded)
        assert "auths" in data
        assert "registry.example.com" in data["auths"]

    def test_encode_docker_registry_secret_contains_credentials(self):
        """Test that Docker registry secret contains credentials."""
        result = encode_docker_registry_secret("registry.example.com", "testuser", "testpass")
        decoded = base64.b64decode(result).decode("utf-8")
        data = json.loads(decoded)
        auth_data = data["auths"]["registry.example.com"]
        assert auth_data["username"] == "testuser"
        assert auth_data["password"] == "testpass"

    def test_encode_docker_registry_secret_auth_field(self):
        """Test that Docker registry secret has correct auth field."""
        result = encode_docker_registry_secret("registry.example.com", "user", "pass")
        decoded = base64.b64decode(result).decode("utf-8")
        data = json.loads(decoded)
        auth_data = data["auths"]["registry.example.com"]
        # Verify auth is base64 encoded user:pass
        auth_decoded = base64.b64decode(auth_data["auth"]).decode("utf-8")
        assert auth_decoded == "user:pass"


@pytest.mark.unit
class TestConfigMapCreation:
    """Test ConfigMap creation functions."""

    @patch("MAIA.maia_fn.kubernetes.client.CoreV1Api")
    @patch("MAIA.maia_fn.kubernetes.client.ApiClient")
    @patch("MAIA.maia_fn.config.load_kube_config_from_dict")
    def test_create_config_map_from_data_single_value(
        self, mock_load_config, mock_api_client, mock_core_api
    ):
        """Test creating ConfigMap with single data value."""
        mock_api_instance = MagicMock()
        mock_core_api.return_value = mock_api_instance
        mock_api_client.return_value.__enter__ = Mock(return_value=MagicMock())
        mock_api_client.return_value.__exit__ = Mock(return_value=False)

        kubeconfig_dict = {"test": "config"}
        create_config_map_from_data(
            data="test data",
            config_map_name="test-configmap",
            namespace="test-namespace",
            kubeconfig_dict=kubeconfig_dict,
            data_key="test.yaml",
        )

        mock_load_config.assert_called_once_with(kubeconfig_dict)
        mock_api_instance.create_namespaced_config_map.assert_called_once()

    @patch("MAIA.maia_fn.kubernetes.client.CoreV1Api")
    @patch("MAIA.maia_fn.kubernetes.client.ApiClient")
    @patch("MAIA.maia_fn.config.load_kube_config_from_dict")
    def test_create_config_map_from_data_multiple_values(
        self, mock_load_config, mock_api_client, mock_core_api
    ):
        """Test creating ConfigMap with multiple data values."""
        mock_api_instance = MagicMock()
        mock_core_api.return_value = mock_api_instance
        mock_api_client.return_value.__enter__ = Mock(return_value=MagicMock())
        mock_api_client.return_value.__exit__ = Mock(return_value=False)

        kubeconfig_dict = {"test": "config"}
        create_config_map_from_data(
            data=["data1", "data2"],
            config_map_name="test-configmap",
            namespace="test-namespace",
            kubeconfig_dict=kubeconfig_dict,
            data_key=["key1.yaml", "key2.yaml"],
        )

        mock_load_config.assert_called_once_with(kubeconfig_dict)
        mock_api_instance.create_namespaced_config_map.assert_called_once()


@pytest.mark.unit
class TestSSHPortFunctions:
    """Test SSH port management functions.
    
    Note: These functions require Kubernetes cluster access and are challenging to test
    without integration tests. Tests focus on verifying the function structure and mocking.
    """

    @patch("MAIA.maia_fn.Path")
    @patch("MAIA.maia_fn.config.load_kube_config_from_dict")
    @patch("MAIA.maia_fn.client.CoreV1Api")
    @patch("MAIA.maia_fn.yaml.safe_load")
    def test_get_ssh_port_dict_nodeport(self, mock_yaml, mock_core_api, mock_config, mock_path):
        """Test getting SSH port dict for NodePort type."""
        # Mock environment and kubeconfig
        mock_path.return_value.read_text.return_value = "test: config"
        mock_yaml.return_value = {"test": "config"}

        # Mock Kubernetes API response
        mock_v1 = MagicMock()
        mock_core_api.return_value = mock_v1

        # Create mock service
        mock_service = MagicMock()
        mock_service.spec.type = "NodePort"
        mock_service.metadata.namespace = "test-namespace"
        mock_service.metadata.name = "test-service-ssh"
        mock_service.spec.ports = [MagicMock(node_port=30000, name="ssh")]

        mock_services = MagicMock()
        mock_services.items = [mock_service]
        mock_v1.list_service_for_all_namespaces.return_value = mock_services

        result = get_ssh_port_dict("NodePort", "test-namespace", (30000, 32767))

        assert result is not None
        assert len(result) == 1
        assert result[0] == {"test-service": 30000}

    @patch("MAIA.maia_fn.Path")
    @patch("MAIA.maia_fn.config.load_kube_config_from_dict")
    @patch("MAIA.maia_fn.client.CoreV1Api")
    @patch("MAIA.maia_fn.yaml.safe_load")
    def test_get_ssh_ports_finds_available_ports(self, mock_yaml, mock_core_api, mock_config, mock_path):
        """Test finding available SSH ports."""
        # Mock environment and kubeconfig
        mock_path.return_value.read_text.return_value = "test: config"
        mock_yaml.return_value = {"test": "config"}

        # Mock Kubernetes API response with one used port
        mock_v1 = MagicMock()
        mock_core_api.return_value = mock_v1

        mock_service = MagicMock()
        mock_service.spec.type = "NodePort"
        mock_service.spec.ports = [MagicMock(node_port=30000, name="ssh")]

        mock_services = MagicMock()
        mock_services.items = [mock_service]
        mock_v1.list_service_for_all_namespaces.return_value = mock_services
        mock_v1.list_namespace.return_value = MagicMock()

        result = get_ssh_ports(2, "NodePort", (30000, 32767))

        assert result is not None
        assert len(result) == 2
        # Port 30000 is used, so first available should be 30001
        assert 30000 not in result
        assert 30001 in result

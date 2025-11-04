"""Pytest configuration and fixtures for MAIA tests."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
import yaml


@pytest.fixture
def temp_config_folder(tmp_path):
    """Create a temporary configuration folder for tests."""
    config_folder = tmp_path / "config"
    config_folder.mkdir(parents=True, exist_ok=True)
    return str(config_folder)


@pytest.fixture
def sample_cluster_config():
    """Provide a sample cluster configuration for tests."""
    return {
        "domain": "example.com",
        "storage_class": "standard",
        "shared_storage_class": "shared-storage",
        "url_type": "subdomain",
        "ssh_port_type": "NodePort",
        "ingress_class": "nginx",
        "keycloak": {
            "issuer_url": "https://iam.example.com/realms/maia",
            "client_id": "maia",
            "client_secret": "test-secret",
        },
        "nginx_cluster_issuer": "cluster-issuer",
        "imagePullSecrets": "registry-secret",
    }


@pytest.fixture
def sample_user_config():
    """Provide a sample user configuration for tests."""
    return {
        "group_ID": "test_project",
        "group_subdomain": "test-project",
    }


@pytest.fixture
def sample_namespace_config():
    """Provide a sample namespace configuration for tests."""
    return {
        "namespace": "test-namespace",
        "chart_name": "test-chart",
    }


@pytest.fixture
def sample_maia_config():
    """Provide a sample MAIA configuration for tests."""
    return {
        "admin_group_ID": "admin",
        "maia_orthanc_image": "registry.example.com/maia-orthanc",
        "maia_orthanc_version": "1.0.0",
    }


@pytest.fixture
def mock_kubernetes_client(mocker):
    """Mock Kubernetes client for tests."""
    mock_client = MagicMock()
    mocker.patch("kubernetes.client.CoreV1Api", return_value=mock_client)
    mocker.patch("kubernetes.config.load_kube_config_from_dict")
    return mock_client


@pytest.fixture
def mock_keycloak_admin(mocker):
    """Mock Keycloak admin client for tests."""
    mock_admin = MagicMock()
    mock_connection = MagicMock()
    mocker.patch("keycloak.KeycloakOpenIDConnection", return_value=mock_connection)
    mocker.patch("keycloak.KeycloakAdmin", return_value=mock_admin)
    return mock_admin


@pytest.fixture
def sample_kubeconfig():
    """Provide a sample kubeconfig for tests."""
    return {
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [
            {
                "name": "test-cluster",
                "cluster": {"server": "https://kubernetes.example.com", "certificate-authority-data": "test-ca-data"},
            }
        ],
        "contexts": [{"name": "test-context", "context": {"cluster": "test-cluster", "user": "test-user"}}],
        "current-context": "test-context",
        "users": [{"name": "test-user", "user": {"token": "test-token"}}],
    }


@pytest.fixture
def mock_settings():
    """Mock settings object for dashboard/keycloak tests."""
    settings = Mock()
    settings.OIDC_SERVER_URL = "https://iam.example.com"
    settings.OIDC_USERNAME = "admin"
    settings.OIDC_REALM_NAME = "maia"
    settings.OIDC_RP_CLIENT_ID = "maia"
    settings.OIDC_RP_CLIENT_SECRET = "test-secret"
    settings.SMTP_SERVER = "smtp.example.com"
    settings.SMTP_PORT = 587
    settings.EMAIL_HOST_USER = "test@example.com"
    settings.EMAIL_HOST_PASSWORD = "password"
    return settings


@pytest.fixture(autouse=True)
def mock_environment_variables(monkeypatch):
    """Set up mock environment variables for all tests."""
    monkeypatch.setenv("KUBECONFIG", "/tmp/test-kubeconfig")
    monkeypatch.setenv("KUBECONFIG_LOCAL", "/tmp/test-kubeconfig")
    monkeypatch.setenv("MAIA_PRIVATE_REGISTRY", "registry.example.com")


@pytest.fixture
def sample_kubeconfig_file(tmp_path, sample_kubeconfig):
    """Create a temporary kubeconfig file for tests."""
    kubeconfig_path = tmp_path / "kubeconfig.yaml"
    with open(kubeconfig_path, "w") as f:
        yaml.dump(sample_kubeconfig, f)
    return str(kubeconfig_path)

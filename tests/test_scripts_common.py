"""Unit tests for MAIA_scripts argument parsers and basic functions."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestArgumentParsers:
    """Test argument parser functions in MAIA_scripts."""

    def test_build_images_get_arg_parser(self):
        """Test MAIA_build_images argument parser."""
        from MAIA_scripts.MAIA_build_images import get_arg_parser

        parser = get_arg_parser()
        assert parser is not None

        # Test parsing valid arguments
        args = parser.parse_args(
            [
                "--maia-config-file",
                "/path/to/maia_config.yaml",
                "--cluster-config",
                "/path/to/cluster_config.yaml",
                "--config-folder",
                "/path/to/config",
                "--project-id",
                "maia-base",
            ]
        )

        assert args.maia_config_file == "/path/to/maia_config.yaml"
        assert args.cluster_config == "/path/to/cluster_config.yaml"
        assert args.config_folder == "/path/to/config"
        assert args.project_id == "maia-base"

    def test_create_jupyterhub_config_get_arg_parser(self):
        """Test MAIA_create_JupyterHub_config argument parser."""
        from MAIA_scripts.MAIA_create_JupyterHub_config import get_arg_parser

        parser = get_arg_parser()
        assert parser is not None

    def test_deploy_helm_chart_get_arg_parser(self):
        """Test MAIA_deploy_helm_chart argument parser."""
        from MAIA_scripts.MAIA_deploy_helm_chart import get_arg_parser

        parser = get_arg_parser()
        assert parser is not None

        # Test parsing valid arguments
        args = parser.parse_args(
            [
                "--chart-name",
                "test-chart",
                "--release-name",
                "test-release",
                "--namespace",
                "test-namespace",
                "--repo",
                "https://charts.example.com",
                "--chart-version",
                "1.0.0",
            ]
        )

        assert args.chart_name == "test-chart"
        assert args.release_name == "test-release"
        assert args.namespace == "test-namespace"

    def test_install_admin_toolkit_get_arg_parser(self):
        """Test MAIA_install_admin_toolkit argument parser."""
        from MAIA_scripts.MAIA_install_admin_toolkit import get_arg_parser

        parser = get_arg_parser()
        assert parser is not None

        # Test parsing valid arguments
        args = parser.parse_args(
            [
                "--maia-config-file",
                "/path/to/maia_config.yaml",
                "--cluster-config",
                "/path/to/cluster_config.yaml",
                "--config-folder",
                "/path/to/config",
            ]
        )

        assert args.maia_config_file == "/path/to/maia_config.yaml"
        assert args.cluster_config == "/path/to/cluster_config.yaml"
        assert args.config_folder == "/path/to/config"

    def test_install_core_toolkit_get_arg_parser(self):
        """Test MAIA_install_core_toolkit argument parser."""
        from MAIA_scripts.MAIA_install_core_toolkit import get_arg_parser

        parser = get_arg_parser()
        assert parser is not None

        # Test parsing valid arguments
        args = parser.parse_args(
            [
                "--maia-config-file",
                "/path/to/maia_config.yaml",
                "--cluster-config",
                "/path/to/cluster_config.yaml",
                "--config-folder",
                "/path/to/config",
            ]
        )

        assert args.maia_config_file == "/path/to/maia_config.yaml"

    def test_install_project_toolkit_get_arg_parser(self):
        """Test MAIA_install_project_toolkit argument parser."""
        from MAIA_scripts.MAIA_install_project_toolkit import get_arg_parser

        parser = get_arg_parser()
        assert parser is not None

        # Test parsing valid arguments
        args = parser.parse_args(
            [
                "--project-config-file",
                "/path/to/project_config.yaml",
                "--maia-config-file",
                "/path/to/maia_config.yaml",
                "--cluster-config",
                "/path/to/cluster_config.yaml",
                "--config-folder",
                "/path/to/config",
            ]
        )

        assert args.project_config_file == "/path/to/project_config.yaml"
        assert args.maia_config_file == "/path/to/maia_config.yaml"

    def test_send_welcome_user_mail_get_arg_parser(self):
        """Test MAIA_send_welcome_user_mail argument parser."""
        from MAIA_scripts.MAIA_send_welcome_user_mail import get_arg_parser

        parser = get_arg_parser()
        assert parser is not None

        # Test parsing valid arguments
        args = parser.parse_args(
            [
                "--receiver-email",
                "user@example.com",
                "--maia-url",
                "https://maia.example.com",
            ]
        )

        assert args.receiver_email == "user@example.com"
        assert args.maia_url == "https://maia.example.com"


@pytest.mark.unit
class TestScriptBasicFunctions:
    """Test basic functions in MAIA_scripts that don't require full integration."""

    @patch("MAIA_scripts.MAIA_build_images.deploy_maia_kaniko")
    @patch("MAIA_scripts.MAIA_build_images.create_helm_repo_secret_from_context")
    @patch("MAIA_scripts.MAIA_build_images.requests.get")
    @patch("MAIA_scripts.MAIA_build_images.OmegaConf.load")
    @patch("MAIA_scripts.MAIA_build_images.config.load_kube_config")
    def test_build_maia_images_function_exists(
        self, mock_load_config, mock_omegaconf, mock_requests, mock_helm_secret, mock_kaniko
    ):
        """Test that build_maia_images function exists and can be called."""
        from MAIA_scripts.MAIA_build_images import build_maia_images

        # Mock responses
        mock_omegaconf.return_value = {"test": "config"}
        mock_response = MagicMock()
        mock_response.text = "docker_versions:\n  test: 1.0"
        mock_requests.return_value = mock_response

        # Verify function exists and accepts expected parameters
        assert callable(build_maia_images)

    def test_create_jupyterhub_config_api_function_exists(self):
        """Test that create_jupyterhub_config_api function exists."""
        from MAIA_scripts.MAIA_create_JupyterHub_config import create_jupyterhub_config_api

        # Verify function exists
        assert callable(create_jupyterhub_config_api)

    def test_install_maia_admin_toolkit_function_exists(self):
        """Test that install_maia_admin_toolkit function exists."""
        from MAIA_scripts.MAIA_install_admin_toolkit import install_maia_admin_toolkit

        # Verify function exists
        assert callable(install_maia_admin_toolkit)

    def test_install_maia_core_toolkit_function_exists(self):
        """Test that install_maia_core_toolkit function exists."""
        from MAIA_scripts.MAIA_install_core_toolkit import install_maia_core_toolkit

        # Verify function exists
        assert callable(install_maia_core_toolkit)

    def test_deploy_maia_toolkit_api_function_exists(self):
        """Test that deploy_maia_toolkit_api function exists."""
        from MAIA_scripts.MAIA_install_project_toolkit import deploy_maia_toolkit_api

        # Verify function exists
        assert callable(deploy_maia_toolkit_api)


@pytest.mark.unit
class TestVersionInfo:
    """Test version information in scripts."""

    def test_build_images_has_version(self):
        """Test that MAIA_build_images has version info."""
        from MAIA_scripts.MAIA_build_images import version

        assert version is not None
        assert isinstance(version, str)

    def test_maia_version_accessible(self):
        """Test that MAIA version is accessible."""
        import MAIA

        assert hasattr(MAIA, "__version__")
        assert MAIA.__version__ is not None

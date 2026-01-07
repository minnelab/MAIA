"""Unit tests for MAIA package initialization and versioning."""
from __future__ import annotations

import pytest


@pytest.mark.unit
class TestMAIAPackage:
    """Test MAIA package structure and imports."""

    def test_maia_package_imports(self):
        """Test that MAIA package can be imported."""
        import MAIA

        assert MAIA is not None

    def test_maia_has_version(self):
        """Test that MAIA package has version attribute."""
        import MAIA

        assert hasattr(MAIA, "__version__")
        assert MAIA.__version__ is not None

    def test_maia_version_is_string(self):
        """Test that MAIA version is a string."""
        import MAIA

        assert isinstance(MAIA.__version__, str)
        assert len(MAIA.__version__) > 0

    def test_maia_modules_importable(self):
        """Test that main MAIA modules can be imported."""
        import MAIA.maia_fn
        import MAIA.keycloak_utils
        import MAIA.kubernetes_utils
        import MAIA.dashboard_utils
        import MAIA.helm_values
        import MAIA.maia_admin
        import MAIA.maia_core

        # Just verify imports work
        assert MAIA.maia_fn is not None
        assert MAIA.keycloak_utils is not None
        assert MAIA.kubernetes_utils is not None


@pytest.mark.unit
class TestMAIAScripts:
    """Test MAIA_scripts package structure."""

    def test_maia_scripts_package_imports(self):
        """Test that MAIA_scripts package can be imported."""
        import MAIA_scripts

        assert MAIA_scripts is not None

    def test_maia_scripts_modules_importable(self):
        """Test that MAIA_scripts modules can be imported."""
        from MAIA_scripts import MAIA_deploy_helm_chart
        from MAIA_scripts import MAIA_send_welcome_user_mail
        from MAIA_scripts import MAIA_send_all_user_email

        assert MAIA_deploy_helm_chart is not None
        assert MAIA_send_welcome_user_mail is not None
        assert MAIA_send_all_user_email is not None


@pytest.mark.unit  
class TestVersionModule:
    """Test version module functionality."""

    def test_version_module_has_get_versions(self):
        """Test that _version module has get_versions function."""
        from MAIA import _version

        assert hasattr(_version, "get_versions")
        assert callable(_version.get_versions)

    def test_get_versions_returns_dict(self):
        """Test that get_versions returns a dictionary."""
        from MAIA import _version

        versions = _version.get_versions()
        assert isinstance(versions, dict)

    def test_get_versions_has_version_key(self):
        """Test that get_versions returns dict with version key."""
        from MAIA import _version

        versions = _version.get_versions()
        assert "version" in versions
        assert isinstance(versions["version"], str)


@pytest.mark.unit
class TestPackageStructure:
    """Test package structure and organization."""

    def test_maia_fn_has_expected_functions(self):
        """Test that maia_fn module has expected functions."""
        from MAIA import maia_fn

        expected_functions = [
            "generate_random_password",
            "generate_human_memorable_password",
            "convert_username_to_jupyterhub_username",
            "encode_docker_registry_secret",
            "create_config_map_from_data",
            "get_ssh_ports",
            "deploy_oauth2_proxy",
            "deploy_mysql",
            "deploy_mlflow",
            "deploy_orthanc",
            "gpu_list_from_nodes",
        ]

        for func_name in expected_functions:
            assert hasattr(maia_fn, func_name)
            assert callable(getattr(maia_fn, func_name))

    def test_keycloak_utils_has_expected_functions(self):
        """Test that keycloak_utils module has expected functions."""
        from MAIA import keycloak_utils

        expected_functions = [
            "get_user_ids",
            "get_groups_for_user",
            "register_user_in_keycloak",
            "register_group_in_keycloak",
            "delete_group_in_keycloak",
        ]

        for func_name in expected_functions:
            assert hasattr(keycloak_utils, func_name)
            assert callable(getattr(keycloak_utils, func_name))

    def test_dashboard_utils_has_expected_functions(self):
        """Test that dashboard_utils module has expected functions."""
        from MAIA import dashboard_utils

        expected_functions = [
            "verify_gpu_availability",
            "verify_gpu_booking_policy",
            "generate_encryption_keys",
            "encrypt_string",
            "decrypt_string",
        ]

        for func_name in expected_functions:
            assert hasattr(dashboard_utils, func_name)
            assert callable(getattr(dashboard_utils, func_name))

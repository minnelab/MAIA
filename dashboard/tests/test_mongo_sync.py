import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ENV_VARS = {
    "DB_USERNAME": "user",
    "DB_PASS": "pass",
    "DB_HOST": "localhost",
    "DB_PORT": "27017",
    "DB_NAME": "testdb",
}


def _make_mongo_mock(projects, users):
    """Return a patched MongoClient whose collections return the given data."""
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_client.__getitem__.return_value = mock_db

    mock_project_col = MagicMock()
    mock_user_col = MagicMock()

    mock_project_col.find.return_value = iter(projects)
    mock_user_col.find.return_value = iter(users)

    def _get_collection(name):
        if name == "maia_projects":
            return mock_project_col
        if name == "maia_users":
            return mock_user_col
        raise KeyError(name)

    mock_db.__getitem__.side_effect = _get_collection
    return mock_client


def _run_main(projects, users, env=None, tmp_path=None):
    """
    Execute mongo_sync.main() with mocked MongoDB and optionally
    inside a temporary directory so that file writes land in tmp_path.
    """
    from dashboard.core import mongo_sync

    env = {**ENV_VARS, **(env or {})}
    mock_client = _make_mongo_mock(projects, users)

    with patch.dict(os.environ, env, clear=False), patch(
        "dashboard.core.mongo_sync.MongoClient", return_value=mock_client
    ):
        if tmp_path is not None:
            orig_dir = os.getcwd()
            os.chdir(tmp_path)
            try:
                mongo_sync.main()
            finally:
                os.chdir(orig_dir)
        else:
            mongo_sync.main()


# ---------------------------------------------------------------------------
# Environment variable loading
# ---------------------------------------------------------------------------


class TestEnvironmentVariables:
    def test_missing_env_var_raises_key_error(self, tmp_path):
        """main() must fail immediately when a required env var is absent."""
        from dashboard.core import mongo_sync

        incomplete_env = {k: v for k, v in ENV_VARS.items() if k != "DB_USERNAME"}
        # Ensure DB_USERNAME is absent from the environment
        env_without_var = {**incomplete_env}

        with patch("dashboard.core.mongo_sync.MongoClient"):
            with patch.dict(os.environ, env_without_var, clear=True):
                with pytest.raises(KeyError):
                    mongo_sync.main()

    def test_env_vars_passed_to_mongo_client(self, tmp_path):
        """MongoClient is called with values taken from the environment."""
        from dashboard.core import mongo_sync

        projects = [{"namespace": "ns1", "description": "d"}]
        users = []
        mock_client = _make_mongo_mock(projects, users)

        with patch.dict(os.environ, ENV_VARS, clear=False), patch(
            "dashboard.core.mongo_sync.MongoClient", return_value=mock_client
        ) as mock_cls:
            orig_dir = os.getcwd()
            os.chdir(tmp_path)
            try:
                mongo_sync.main()
            finally:
                os.chdir(orig_dir)

        mock_cls.assert_called_once_with(
            host="localhost",
            port=27017,
            username="user",
            password="pass",
            authSource="admin",
        )


# ---------------------------------------------------------------------------
# User namespace filtering
# ---------------------------------------------------------------------------


class TestUserNamespaceFiltering:
    def test_user_matching_exact_namespace_is_included(self, tmp_path):
        """A user whose namespace matches the project namespace is included."""
        projects = [{"namespace": "my-project"}]
        users = [{"namespace": "my-project", "email": "alice@example.com"}]

        _run_main(projects, users, tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "my-project.json").read_text())
        assert result["users"] == ["alice@example.com"]

    def test_user_with_comma_separated_namespaces_matched(self, tmp_path):
        """A user with a comma-separated namespace list is matched correctly."""
        projects = [{"namespace": "proj-b"}]
        users = [{"namespace": "proj-a, proj-b, proj-c", "email": "bob@example.com"}]

        _run_main(projects, users, tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "proj-b.json").read_text())
        assert "bob@example.com" in result["users"]

    def test_user_not_in_namespace_excluded(self, tmp_path):
        """A user whose namespace does not match the project is excluded."""
        projects = [{"namespace": "proj-a"}]
        users = [{"namespace": "proj-b", "email": "carol@example.com"}]

        _run_main(projects, users, tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "proj-a.json").read_text())
        assert result["users"] == []

    def test_user_without_email_excluded(self, tmp_path):
        """A matching user with no email field is not added to the users list."""
        projects = [{"namespace": "proj-x"}]
        users = [{"namespace": "proj-x"}]  # no "email" key

        _run_main(projects, users, tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "proj-x.json").read_text())
        assert result["users"] == []

    def test_user_with_none_namespace_excluded(self, tmp_path):
        """A user whose namespace value is None is treated as empty string."""
        projects = [{"namespace": "ns"}]
        users = [{"namespace": None, "email": "dave@example.com"}]

        _run_main(projects, users, tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "ns.json").read_text())
        assert result["users"] == []

    def test_multiple_users_same_namespace(self, tmp_path):
        """Multiple users belonging to the same namespace are all included."""
        projects = [{"namespace": "shared"}]
        users = [
            {"namespace": "shared", "email": "user1@example.com"},
            {"namespace": "shared", "email": "user2@example.com"},
        ]

        _run_main(projects, users, tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "shared.json").read_text())
        assert sorted(result["users"]) == ["user1@example.com", "user2@example.com"]

    def test_users_field_in_project_document_is_ignored(self, tmp_path):
        """The 'users' field on the project document itself must not overwrite filtered users."""
        projects = [{"namespace": "ns", "users": ["should-be-ignored@example.com"]}]
        users = [{"namespace": "ns", "email": "real@example.com"}]

        _run_main(projects, users, tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "ns.json").read_text())
        assert result["users"] == ["real@example.com"]

    def test_namespace_with_spaces_in_user_list_stripped(self, tmp_path):
        """Spaces around namespace entries in user's comma-separated list are stripped."""
        projects = [{"namespace": "trimmed"}]
        users = [{"namespace": "  trimmed  ", "email": "eve@example.com"}]

        _run_main(projects, users, tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "trimmed.json").read_text())
        assert result["users"] == ["eve@example.com"]


# ---------------------------------------------------------------------------
# Date field processing
# ---------------------------------------------------------------------------


class TestDateFieldProcessing:
    def test_date_as_dict_with_dollar_date_z_suffix(self, tmp_path):
        """date stored as {'$date': '<ISO>Z'} is formatted to YYYY-MM-DD."""
        projects = [{"namespace": "ns", "date": {"$date": "2023-06-15T00:00:00Z"}}]
        _run_main(projects, [], tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "ns.json").read_text())
        assert result["date"] == "2023-06-15"

    def test_date_as_dict_invalid_value_kept_as_is(self, tmp_path):
        """date dict with an unparseable value is stored verbatim."""
        projects = [{"namespace": "ns", "date": {"$date": "not-a-date"}}]
        _run_main(projects, [], tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "ns.json").read_text())
        assert result["date"] == "not-a-date"

    def test_date_as_iso_string(self, tmp_path):
        """date stored as an ISO string is formatted to YYYY-MM-DD."""
        projects = [{"namespace": "ns", "date": "2024-01-20T10:30:00Z"}]
        _run_main(projects, [], tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "ns.json").read_text())
        assert result["date"] == "2024-01-20"

    def test_date_as_datetime_object(self, tmp_path):
        """date stored as a Python datetime is formatted to YYYY-MM-DD."""
        projects = [{"namespace": "ns", "date": datetime(2022, 3, 5, 12, 0, 0)}]
        _run_main(projects, [], tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "ns.json").read_text())
        assert result["date"] == "2022-03-05"

    def test_date_as_other_type_converted_to_string(self, tmp_path):
        """date stored as an integer (or other non-standard type) falls back to str()."""
        projects = [{"namespace": "ns", "date": 20230615}]
        _run_main(projects, [], tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "ns.json").read_text())
        assert result["date"] == "20230615"

    def test_date_as_unparseable_string_kept_as_is(self, tmp_path):
        """date as a string that cannot be parsed as ISO is stored as-is."""
        projects = [{"namespace": "ns", "date": "totally-invalid"}]
        _run_main(projects, [], tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "ns.json").read_text())
        assert result["date"] == "totally-invalid"

    def test_date_timezone_aware_iso_string(self, tmp_path):
        """date ISO string with explicit timezone offset is handled correctly."""
        projects = [{"namespace": "ns", "date": "2023-11-30T23:59:59+05:30"}]
        _run_main(projects, [], tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "ns.json").read_text())
        assert result["date"] == "2023-11-30"


# ---------------------------------------------------------------------------
# Metadata field filtering
# ---------------------------------------------------------------------------


class TestMetadataFiltering:
    METADATA_FIELDS = [
        "namespace",
        "email",
        "users",
        "memory_limit",
        "cpu_limit",
        "memory_request",
        "cpu_request",
        "project_tier",
        "gpu",
        "cluster",
        "date",
        "supervisor",
        "description",
        "auto_deploy",
        "auto_deploy_apps",
        "project_configuration",
    ]

    def test_only_metadata_fields_included(self, tmp_path):
        """Fields not in the metadata list must be absent from the output."""
        projects = [
            {
                "namespace": "ns",
                "_id": "mongo-object-id",
                "internal_field": "secret",
                "description": "public",
            }
        ]
        _run_main(projects, [], tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "ns.json").read_text())
        assert "_id" not in result
        assert "internal_field" not in result
        assert result["description"] == "public"

    def test_all_standard_metadata_fields_passed_through(self, tmp_path):
        """All fields in the metadata list (except 'date' and 'users') are copied verbatim."""
        project = {
            "namespace": "ns",
            "email": "owner@example.com",
            "memory_limit": "4Gi",
            "cpu_limit": "2",
            "memory_request": "2Gi",
            "cpu_request": "1",
            "project_tier": "standard",
            "gpu": False,
            "cluster": "cluster-1",
            "supervisor": "sup@example.com",
            "description": "A test project",
            "auto_deploy": True,
            "auto_deploy_apps": ["app1"],
            "project_configuration": {"key": "value"},
        }
        projects = [project]
        _run_main(projects, [], tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "ns.json").read_text())
        for field in [
            "namespace",
            "email",
            "memory_limit",
            "cpu_limit",
            "memory_request",
            "cpu_request",
            "project_tier",
            "gpu",
            "cluster",
            "supervisor",
            "description",
            "auto_deploy",
            "auto_deploy_apps",
            "project_configuration",
        ]:
            assert result[field] == project[field], f"Field {field!r} mismatch"


# ---------------------------------------------------------------------------
# Namespace sanitization
# ---------------------------------------------------------------------------


class TestNamespaceSanitization:
    def test_uppercase_converted_to_lowercase(self, tmp_path):
        """Uppercase characters in namespace are lowercased."""
        projects = [{"namespace": "MyProject"}]
        _run_main(projects, [], tmp_path=tmp_path)

        assert (tmp_path / "Projects" / "myproject.json").exists()

    def test_special_characters_replaced_with_underscore(self, tmp_path):
        """Characters outside [a-z0-9-] are replaced with underscores."""
        projects = [{"namespace": "my.project@2024"}]
        _run_main(projects, [], tmp_path=tmp_path)

        assert (tmp_path / "Projects" / "my_project_2024.json").exists()

    def test_hyphens_preserved(self, tmp_path):
        """Hyphens are valid and must be preserved in the filename."""
        projects = [{"namespace": "my-valid-namespace"}]
        _run_main(projects, [], tmp_path=tmp_path)

        assert (tmp_path / "Projects" / "my-valid-namespace.json").exists()

    def test_digits_preserved(self, tmp_path):
        """Digits are valid and must be preserved in the filename."""
        projects = [{"namespace": "project42"}]
        _run_main(projects, [], tmp_path=tmp_path)

        assert (tmp_path / "Projects" / "project42.json").exists()

    def test_empty_namespace_raises_value_error(self, tmp_path):
        """A project with an empty namespace must raise ValueError."""
        projects = [{"namespace": ""}]
        with pytest.raises(ValueError, match="Unsafe or empty namespace"):
            _run_main(projects, [], tmp_path=tmp_path)

    def test_namespace_missing_from_project_raises_value_error(self, tmp_path):
        """A project with no namespace key produces empty string → ValueError."""
        projects = [{"description": "no namespace here"}]
        with pytest.raises((ValueError, KeyError)):
            _run_main(projects, [], tmp_path=tmp_path)

    def test_namespace_with_forward_slash_sanitized(self, tmp_path):
        """Forward slashes are replaced with underscores, preventing path traversal."""
        projects = [{"namespace": "a/b"}]
        _run_main(projects, [], tmp_path=tmp_path)

        # "a/b" → "a_b"
        assert (tmp_path / "Projects" / "a_b.json").exists()

    def test_mixed_case_and_special_chars(self, tmp_path):
        """Mixed-case namespaces with special chars are fully sanitized."""
        projects = [{"namespace": "My Project 2024!"}]
        _run_main(projects, [], tmp_path=tmp_path)

        assert (tmp_path / "Projects" / "my_project_2024_.json").exists()


# ---------------------------------------------------------------------------
# File output
# ---------------------------------------------------------------------------


class TestFileOutput:
    def test_projects_folder_created(self, tmp_path):
        """The Projects/ folder is created if it does not exist."""
        projects = [{"namespace": "ns"}]
        _run_main(projects, [], tmp_path=tmp_path)

        assert (tmp_path / "Projects").is_dir()

    def test_json_file_written_per_project(self, tmp_path):
        """One JSON file per project is written into the Projects/ folder."""
        projects = [
            {"namespace": "proj-a"},
            {"namespace": "proj-b"},
        ]
        _run_main(projects, [], tmp_path=tmp_path)

        assert (tmp_path / "Projects" / "proj-a.json").exists()
        assert (tmp_path / "Projects" / "proj-b.json").exists()

    def test_json_file_is_valid_json(self, tmp_path):
        """Each written file must be parseable as valid JSON."""
        projects = [{"namespace": "ns", "description": "test"}]
        _run_main(projects, [], tmp_path=tmp_path)

        content = (tmp_path / "Projects" / "ns.json").read_text()
        parsed = json.loads(content)
        assert isinstance(parsed, dict)

    def test_json_indented_with_4_spaces(self, tmp_path):
        """JSON output uses 4-space indentation."""
        projects = [{"namespace": "ns", "description": "hello"}]
        _run_main(projects, [], tmp_path=tmp_path)

        raw = (tmp_path / "Projects" / "ns.json").read_text()
        # Verify indented JSON: lines after the opening brace start with 4 spaces
        lines = raw.splitlines()
        indented_lines = [l for l in lines[1:] if l.strip()]
        assert any(l.startswith("    ") for l in indented_lines)

    def test_empty_project_list_creates_no_files(self, tmp_path):
        """No files (other than the Projects/ dir) are created when there are no projects."""
        _run_main([], [], tmp_path=tmp_path)

        project_files = list((tmp_path / "Projects").iterdir()) if (tmp_path / "Projects").exists() else []
        assert project_files == []


# ---------------------------------------------------------------------------
# End-to-end / integration-style
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_full_project_with_all_fields(self, tmp_path):
        """A project with all metadata fields and matching users produces correct output."""
        project = {
            "_id": "irrelevant",
            "namespace": "full-project",
            "email": "owner@example.com",
            "memory_limit": "8Gi",
            "cpu_limit": "4",
            "memory_request": "4Gi",
            "cpu_request": "2",
            "project_tier": "premium",
            "gpu": True,
            "cluster": "prod",
            "date": "2023-07-01T00:00:00Z",
            "supervisor": "boss@example.com",
            "description": "Full project",
            "auto_deploy": False,
            "auto_deploy_apps": [],
            "project_configuration": {},
            "extra_secret": "should_not_appear",
        }
        users = [
            {"namespace": "full-project", "email": "member1@example.com"},
            {"namespace": "other-project", "email": "not-a-member@example.com"},
        ]

        _run_main([project], users, tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "full-project.json").read_text())

        assert result["namespace"] == "full-project"
        assert result["users"] == ["member1@example.com"]
        assert result["date"] == "2023-07-01"
        assert "_id" not in result
        assert "extra_secret" not in result
        assert result["gpu"] is True

    def test_multiple_projects_multiple_users(self, tmp_path):
        """Multiple projects each receive only their own matched users."""
        projects = [
            {"namespace": "alpha"},
            {"namespace": "beta"},
        ]
        users = [
            {"namespace": "alpha", "email": "a1@example.com"},
            {"namespace": "alpha, beta", "email": "shared@example.com"},
            {"namespace": "beta", "email": "b1@example.com"},
        ]

        _run_main(projects, users, tmp_path=tmp_path)

        alpha = json.loads((tmp_path / "Projects" / "alpha.json").read_text())
        beta = json.loads((tmp_path / "Projects" / "beta.json").read_text())

        assert sorted(alpha["users"]) == ["a1@example.com", "shared@example.com"]
        assert sorted(beta["users"]) == ["b1@example.com", "shared@example.com"]

    def test_regression_user_with_empty_email_string_excluded(self, tmp_path):
        """Regression: a user with an empty-string email must not be included."""
        projects = [{"namespace": "ns"}]
        users = [{"namespace": "ns", "email": ""}]

        _run_main(projects, users, tmp_path=tmp_path)

        result = json.loads((tmp_path / "Projects" / "ns.json").read_text())
        # Empty string is falsy → must be excluded
        assert result["users"] == []

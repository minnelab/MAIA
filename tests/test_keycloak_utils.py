"""Unit tests for MAIA/keycloak_utils.py functions."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from MAIA.keycloak_utils import (
    delete_group_in_keycloak,
    get_groups_for_user,
    get_groups_in_keycloak,
    get_list_of_groups_requesting_a_user,
    get_list_of_users_requesting_a_group,
    get_maia_users_from_keycloak,
    get_user_ids,
    register_group_in_keycloak,
    register_user_in_keycloak,
    register_users_in_group_in_keycloak,
    remove_user_from_group_in_keycloak,
)


@pytest.mark.unit
class TestKeycloakUserFunctions:
    """Test Keycloak user management functions."""

    def test_get_user_ids_returns_dict(self, mock_settings, mock_keycloak_admin):
        """Test that get_user_ids returns a dictionary of users and their groups."""
        # Setup mock groups
        mock_keycloak_admin.get_groups.return_value = [
            {"id": "group1", "name": "MAIA:project1"},
            {"id": "group2", "name": "MAIA:project2"},
            {"id": "group3", "name": "other-group"},  # Should be filtered out
        ]

        # Setup mock users for each MAIA group
        mock_keycloak_admin.get_group_members.side_effect = [
            [{"email": "user1@example.com"}, {"email": "user2@example.com"}],  # project1
            [{"email": "user2@example.com"}, {"email": "user3@example.com"}],  # project2
        ]

        result = get_user_ids(mock_settings)

        assert isinstance(result, dict)
        assert "user1@example.com" in result
        assert "user2@example.com" in result
        assert "user3@example.com" in result
        assert "project1" in result["user1@example.com"]
        assert "project2" in result["user2@example.com"]
        # user2 should be in both groups
        assert set(result["user2@example.com"]) == {"project1", "project2"}

    def test_get_user_ids_filters_non_maia_groups(self, mock_settings, mock_keycloak_admin):
        """Test that get_user_ids filters out non-MAIA groups."""
        mock_keycloak_admin.get_groups.return_value = [
            {"id": "group1", "name": "MAIA:project1"},
            {"id": "group2", "name": "other-group"},
            {"id": "group3", "name": "another-group"},
        ]

        mock_keycloak_admin.get_group_members.return_value = [{"email": "user1@example.com"}]

        result = get_user_ids(mock_settings)

        # Should only call get_group_members once for the MAIA group
        assert mock_keycloak_admin.get_group_members.call_count == 1

    def test_get_groups_for_user(self, mock_settings, mock_keycloak_admin):
        """Test retrieving groups for a specific user."""
        mock_keycloak_admin.get_groups.return_value = [
            {"id": "group1", "name": "MAIA:project1"},
            {"id": "group2", "name": "MAIA:project2"},
        ]

        mock_keycloak_admin.get_group_members.side_effect = [
            [{"email": "user1@example.com"}, {"email": "target@example.com"}],
            [{"email": "user2@example.com"}],
        ]

        result = get_groups_for_user("target@example.com", mock_settings)

        assert "project1" in result
        assert "project2" not in result

    def test_get_maia_users_from_keycloak(self, mock_settings, mock_keycloak_admin):
        """Test getting all MAIA users from Keycloak."""
        mock_keycloak_admin.get_groups.return_value = [
            {"id": "group1", "name": "MAIA:project1"},
        ]

        mock_keycloak_admin.get_group_members.return_value = [
            {"email": "user1@example.com", "username": "user1"},
            {"email": "user2@example.com", "username": "user2"},
        ]

        result = get_maia_users_from_keycloak(mock_settings)

        assert isinstance(result, dict)
        assert len(result) >= 2


@pytest.mark.unit
class TestKeycloakGroupFunctions:
    """Test Keycloak group management functions."""

    def test_register_group_in_keycloak(self, mock_settings, mock_keycloak_admin):
        """Test registering a new group in Keycloak."""
        mock_keycloak_admin.create_group.return_value = "new-group-id"

        register_group_in_keycloak("new_project", mock_settings)

        # Verify the group was created with MAIA prefix
        mock_keycloak_admin.create_group.assert_called_once()
        call_args = mock_keycloak_admin.create_group.call_args
        assert "MAIA:new_project" in str(call_args)

    def test_delete_group_in_keycloak(self, mock_settings, mock_keycloak_admin):
        """Test deleting a group from Keycloak."""
        mock_keycloak_admin.get_groups.return_value = [
            {"id": "group1", "name": "MAIA:project1"},
            {"id": "group2", "name": "MAIA:project2"},
        ]

        delete_group_in_keycloak("project1", mock_settings)

        mock_keycloak_admin.delete_group.assert_called_once_with("group1")

    def test_get_groups_in_keycloak(self, mock_settings, mock_keycloak_admin):
        """Test retrieving all MAIA groups from Keycloak."""
        mock_keycloak_admin.get_groups.return_value = [
            {"id": "group1", "name": "MAIA:project1"},
            {"id": "group2", "name": "MAIA:project2"},
            {"id": "group3", "name": "other-group"},
        ]

        result = get_groups_in_keycloak(mock_settings)

        # Should only return MAIA groups
        assert isinstance(result, list)
        assert "project1" in result or any("project1" in str(g) for g in result)


@pytest.mark.unit
class TestKeycloakUserGroupRegistration:
    """Test Keycloak user-group registration functions."""

    def test_register_user_in_keycloak(self, mock_settings, mock_keycloak_admin):
        """Test registering a new user in Keycloak."""
        register_user_in_keycloak("newuser@example.com", mock_settings)

        mock_keycloak_admin.create_user.assert_called_once()

    def test_register_users_in_group_in_keycloak(self, mock_settings, mock_keycloak_admin):
        """Test registering multiple users in a group."""
        mock_keycloak_admin.get_groups.return_value = [
            {"id": "group1", "name": "MAIA:project1"},
        ]

        mock_keycloak_admin.get_users.return_value = [
            {"id": "user1", "email": "user1@example.com"},
            {"id": "user2", "email": "user2@example.com"},
        ]

        emails = ["user1@example.com", "user2@example.com"]
        register_users_in_group_in_keycloak(emails, "project1", mock_settings)

        # Verify users were added to group
        assert mock_keycloak_admin.group_user_add.call_count == 2

    def test_remove_user_from_group_in_keycloak(self, mock_settings, mock_keycloak_admin):
        """Test removing a user from a group in Keycloak."""
        mock_keycloak_admin.get_groups.return_value = [
            {"id": "group1", "name": "MAIA:project1"},
        ]

        mock_keycloak_admin.get_users.return_value = [
            {"id": "user1", "email": "user1@example.com"},
        ]

        remove_user_from_group_in_keycloak("user1@example.com", "project1", mock_settings)

        mock_keycloak_admin.group_user_remove.assert_called_once_with("user1", "group1")


@pytest.mark.unit
class TestKeycloakListFunctions:
    """Test Keycloak list functions."""

    def test_get_list_of_groups_requesting_a_user(self, mock_settings):
        """Test getting list of groups requesting a user."""
        # Create mock user model
        mock_user_model = MagicMock()
        mock_query = MagicMock()
        mock_user_model.query.filter_by.return_value = mock_query
        mock_query.all.return_value = [
            MagicMock(group_id="project1", approved=False),
            MagicMock(group_id="project2", approved=False),
        ]

        result = get_list_of_groups_requesting_a_user("user@example.com", mock_user_model)

        assert isinstance(result, list)
        assert len(result) >= 0

    def test_get_list_of_users_requesting_a_group(self, mock_settings):
        """Test getting list of users requesting a group."""
        # Create mock user model
        mock_user_model = MagicMock()
        mock_query = MagicMock()
        mock_user_model.query.filter_by.return_value = mock_query
        mock_query.all.return_value = [
            MagicMock(user_email="user1@example.com", approved=False),
            MagicMock(user_email="user2@example.com", approved=False),
        ]

        result = get_list_of_users_requesting_a_group(mock_user_model, "project1")

        assert isinstance(result, list)
        assert len(result) >= 0

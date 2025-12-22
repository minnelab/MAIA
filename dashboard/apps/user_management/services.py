"""
Service functions for user and group management.

This module contains reusable functions for managing users and groups,
including MAIA database operations and Keycloak integration.

Usage Examples:
    # Create a new user
    from apps.user_management.services import create_user
    result = create_user(
        email="user@example.com",
        username="johndoe",
        first_name="John",
        last_name="Doe",
        namespace="admin,users,project1"
    )
    
    # Create a new group
    from apps.user_management.services import create_group
    result = create_group(
        group_id="project1",
        gpu="2",
        date="2025-12-22",
        memory_limit="16Gi",
        cpu_limit="4",
        conda="base",
        cluster="cluster1",
        minimal_env="false",
        user_id="admin@example.com",
        user_list=["user1@example.com", "user2@example.com"]
    )
    
    # Delete a user
    from apps.user_management.services import delete_user
    result = delete_user(email="user@example.com")
    
All functions return a dictionary with 'message' and 'status' keys.
"""

from django.conf import settings
from apps.models import MAIAUser, MAIAProject
from MAIA.keycloak_utils import (
    register_user_in_keycloak,
    register_group_in_keycloak,
    register_users_in_group_in_keycloak,
    delete_group_in_keycloak,
    remove_user_from_group_in_keycloak,
    get_list_of_users_requesting_a_group,
    get_maia_users_from_keycloak,
)


def create_user(email, username, first_name, last_name, namespace):
    """
    Create a new MAIA user and register them in Keycloak.
    
    Args:
        email (str): User's email address
        username (str): User's username
        first_name (str): User's first name
        last_name (str): User's last name
        namespace (str): Comma-separated list of namespaces/groups
        
    Returns:
        dict: Success message or error information
    """
    try:
        MAIAUser.objects.create(
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            namespace=namespace
        )
    except Exception as e:
        # If user already exists, update their namespace
        MAIAUser.objects.filter(email=email).update(namespace=namespace)
    
    # Register user in Keycloak
    try:
        register_user_in_keycloak(email=email, settings=settings)
    except Exception as e:
        print(f"Error registering user {email} in Keycloak: {e}")
    
    # Register user in their groups
    for group in namespace.split(","):
        register_users_in_group_in_keycloak(
            group_id=group,
            emails=[email],
            settings=settings
        )
    
    return {"message": "User created successfully", "status": 200}


def update_user(email, namespace):
    """
    Update a user's namespace/groups.
    
    Args:
        email (str): User's email address
        namespace (str): Comma-separated list of namespaces/groups
        
    Returns:
        dict: Success message or error information
    """
    MAIAUser.objects.filter(email=email).update(namespace=namespace)
    return {"message": "User updated successfully", "status": 200}


def delete_user(email):
    """
    Delete a user and remove them from all Keycloak groups.
    
    Args:
        email (str): User's email address
        
    Returns:
        dict: Success message or error information
    """
    user = MAIAUser.objects.filter(email=email).first()
    if user:
        for group in user.namespace.split(","):
            if group not in ["admin", "users"]:
                remove_user_from_group_in_keycloak(
                    email=email,
                    group_id=group,
                    settings=settings
                )
    MAIAUser.objects.filter(email=email).delete()
    
    return {"message": "User deleted successfully", "status": 200}


def create_group(group_id, gpu, date, memory_limit, cpu_limit, conda, cluster, minimal_env, user_id, user_list=None):
    """
    Create a new MAIA group/project and register it in Keycloak.
    
    Args:
        group_id (str): Group identifier (namespace)
        gpu (str): GPU allocation for the group
        date (str): Creation date
        memory_limit (str): Memory limit for the group
        cpu_limit (str): CPU limit for the group
        conda (str): Conda environment configuration
        cluster (str): Cluster assignment
        minimal_env (str): Minimal environment flag
        user_id (str): Email of the user creating/owning the group
        user_list (list, optional): List of user emails to add to the group
        
    Returns:
        dict: Success message or error information
    """
    # Handle user list if provided
    if user_list and len(user_list) > 0:
        try:
            for user_email in user_list:
                user = MAIAUser.objects.filter(email=user_email).first()
                if user:
                    namespace = user.namespace
                    if group_id not in namespace.split(","):
                        namespace = namespace + "," + group_id
                        user.namespace = namespace
                        user.save()
                    register_users_in_group_in_keycloak(
                        group_id=group_id,
                        emails=[user_email],
                        settings=settings
                    )
            
            # Remove users not in the new list
            registered_users = get_list_of_users_requesting_a_group(
                group_id=group_id,
                maia_user_model=MAIAUser
            )
            if len(registered_users) > 0:
                for user_email in registered_users:
                    if user_email not in user_list:
                        user = MAIAUser.objects.filter(email=user_email).first()
                        if user:
                            namespace = user.namespace
                            if group_id in namespace.split(","):
                                namespace = namespace.replace(group_id, "").replace(",,", ",")
                                if namespace.endswith(","):
                                    namespace = namespace[:-1]
                                user.namespace = namespace
                                user.save()
            
            # Clean up Keycloak groups
            users = get_maia_users_from_keycloak(settings=settings)
            for user in users:
                if user["email"] not in user_list and "MAIA:" + group_id in user["groups"]:
                    remove_user_from_group_in_keycloak(
                        email=user["email"],
                        group_id=group_id,
                        settings=settings
                    )
        except Exception as e:
            print(f"Error parsing user list: {e}")
            return {"message": f"Error parsing user list: {e}", "status": 400}
    
    # Create or update the project
    try:
        MAIAProject.objects.create(
            namespace=group_id,
            email=user_id,
            gpu=gpu,
            date=date,
            memory_limit=memory_limit,
            cpu_limit=cpu_limit,
            conda=conda,
            cluster=cluster,
            minimal_env=minimal_env
        )
    except Exception as e:
        MAIAProject.objects.filter(namespace=group_id).update(
            email=user_id,
            gpu=gpu,
            date=date,
            memory_limit=memory_limit,
            cpu_limit=cpu_limit,
            conda=conda,
            cluster=cluster,
            minimal_env=minimal_env
        )
    
    # Register group in Keycloak
    try:
        register_group_in_keycloak(group_id=group_id, settings=settings)
    except Exception as e:
        print(f"Error registering group {group_id} in Keycloak: {e}")
    
    # Add the owner to the group
    register_users_in_group_in_keycloak(
        group_id=group_id,
        emails=[user_id],
        settings=settings
    )
    user = MAIAUser.objects.filter(email=user_id).first()
    namespace = user.namespace
    if group_id not in namespace.split(","):
        namespace = namespace + "," + group_id
        user.namespace = namespace
        user.save()
    
    # Register all users in the group
    users_in_group = get_list_of_users_requesting_a_group(
        group_id=group_id,
        maia_user_model=MAIAUser
    )
    for user_email in users_in_group:
        register_users_in_group_in_keycloak(
            group_id=group_id,
            emails=[user_email],
            settings=settings
        )
    
    return {"message": "Group created successfully", "status": 200}


def delete_group(group_id):
    """
    Delete a group and remove it from Keycloak.
    
    Args:
        group_id (str): Group identifier (namespace)
        
    Returns:
        dict: Success message or error information
    """
    MAIAProject.objects.filter(namespace=group_id).delete()
    delete_group_in_keycloak(group_id=group_id, settings=settings)
    
    # Remove all users from the group in Keycloak
    users_in_group = get_list_of_users_requesting_a_group(
        group_id=group_id,
        maia_user_model=MAIAUser
    )
    for user in users_in_group:
        remove_user_from_group_in_keycloak(
            email=user.email,
            group_id=group_id,
            settings=settings
        )
    
    return {"message": "Group deleted successfully", "status": 200}

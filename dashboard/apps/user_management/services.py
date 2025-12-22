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

import logging
from django.conf import settings
from django.db import IntegrityError
from keycloak.exceptions import KeycloakPostError
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

logger = logging.getLogger(__name__)


def _add_group_to_namespace(namespace, group_id):
    """
    Helper function to safely add a group to a namespace string.
    
    Args:
        namespace (str): Comma-separated namespace string (can be None or empty)
        group_id (str): Group ID to add
        
    Returns:
        str: Updated namespace string
    """
    if not namespace:
        return group_id
    
    groups = [g.strip() for g in namespace.split(",") if g.strip()]
    if group_id not in groups:
        groups.append(group_id)
    return ",".join(groups)


def _remove_group_from_namespace(namespace, group_id):
    """
    Helper function to safely remove a group from a namespace string.
    
    Args:
        namespace (str): Comma-separated namespace string (can be None or empty)
        group_id (str): Group ID to remove
        
    Returns:
        str: Updated namespace string
    """
    if not namespace:
        return ""
    
    groups = [g.strip() for g in namespace.split(",") if g.strip()]
    if group_id in groups:
        groups.remove(group_id)
    return ",".join(groups)


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
    except IntegrityError as e:
        # If user already exists, update their namespace
        MAIAUser.objects.filter(email=email).update(namespace=namespace)
    
    # Register user in Keycloak
    try:
        register_user_in_keycloak(email=email, settings=settings)
        user_already_exists = False
    except KeycloakPostError as e:
        logger.error(f"Error registering user {email} in Keycloak: {e}")
        user_already_exists = True
    
    # Register user in their groups
    if namespace:
        groups = [g.strip() for g in namespace.split(",") if g.strip()]
        for group in groups:
            register_users_in_group_in_keycloak(
                group_id=group,
                emails=[email],
                settings=settings
            )
    
    return {"message": "User already exists in Keycloak" if user_already_exists else "User created successfully", "status": 200}


def update_user(email, namespace):
    """
    Update a user's namespace/groups.
    
    Args:
        email (str): User's email address
        namespace (str): Comma-separated list of namespaces/groups
        
    Returns:
        dict: Success message or error information
    """
    user_qs = MAIAUser.objects.filter(email=email)  
    user = user_qs.first() 
    # If user does not exist in the database, there is nothing to sync in Keycloak  
    if not user:  
        return {"message": "User updated successfully", "status": 200}   
    old_namespace = user.namespace if user else None  

    # Update namespace in the MAIA database  
    user_qs.update(namespace=namespace)  



    # Normalize namespaces to sets of group IDs  
    old_groups = {  
        g.strip() for g in (old_namespace or "").split(",") if g.strip()  
    }  
    new_groups = {  
        g.strip() for g in (namespace or "").split(",") if g.strip()  
    }  

    groups_to_add = new_groups - old_groups  
    groups_to_remove = old_groups - new_groups  

    # Add user to newly assigned groups in Keycloak  
    for group in groups_to_add:  
        try:  
            register_users_in_group_in_keycloak(  
                group_id=group,  
                emails=[email],  
                settings=settings,  
            )  
        except Exception as e:  
            logger.error(  
                f"Error adding user {email} to group {group} in Keycloak during update: {e}"  
            )  

    # Remove user from groups they are no longer part of in Keycloak  
    for group in groups_to_remove:  
        # Keep behavior consistent with delete_user: do not remove from reserved groups  
        if group in ["admin", "users"]:  
            continue  
        try:  
            remove_user_from_group_in_keycloak(  
                email=email,  
                group_id=group,  
                settings=settings,  
            )  
        except Exception as e:  
            logger.error(  
                f"Error removing user {email} from group {group} in Keycloak during update: {e}"  
            )  
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
    if not user:
        return {"message": "User deleted successfully", "status": 200}
    else:
        user = MAIAUser.objects.filter(email=email).delete()
    if user.namespace:
        groups = [g.strip() for g in user.namespace.split(",") if g.strip()]
        for group in groups:
            if group not in ["admin", "users"]:
                remove_user_from_group_in_keycloak(
                    email=email,
                    group_id=group,
                    settings=settings
                )
    
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
    if user_list is not None and not isinstance(user_list, list): 
        return {"message": "User list must be a list", "status": 400}
    try:
        register_group_in_keycloak(group_id=group_id, settings=settings)
        group_already_exists = False
    except KeycloakPostError as e:
        group_already_exists = True
        logger.error(f"Error registering group {group_id} in Keycloak: {e}")

    if user_list and len(user_list) > 0:
        try:
            # Batch-fetch users to avoid N+1 queries  
            users_by_email = {  
                user.email: user  
                for user in MAIAUser.objects.filter(email__in=user_list)  
            }  

            users_to_update = []  
            emails_to_add_in_keycloak = []  

            # Update namespaces in memory and prepare batched Keycloak registration  
            for user_email in user_list:  
                user = users_by_email.get(user_email)  
                if user:  
                    user.namespace = _add_group_to_namespace(user.namespace, group_id)  
                    users_to_update.append(user)  
                    emails_to_add_in_keycloak.append(user_email)  

            if users_to_update:  
                MAIAUser.objects.bulk_update(users_to_update, ["namespace"])  

            if emails_to_add_in_keycloak:  
                register_users_in_group_in_keycloak(  
                    group_id=group_id,  
                    emails=emails_to_add_in_keycloak,  
                    settings=settings,  
                )  

            # Remove users not in the new list  
            registered_users = get_list_of_users_requesting_a_group(  
                group_id=group_id,  
                maia_user_model=MAIAUser  
            )  
            if len(registered_users) > 0:  
                emails_to_remove = [  
                    user_email for user_email in registered_users  
                    if user_email not in user_list  
                ]  
                if emails_to_remove:  
                    users_to_update = []  
                    for user in MAIAUser.objects.filter(email__in=emails_to_remove):  
                        user.namespace = _remove_group_from_namespace(user.namespace, group_id)  
                        users_to_update.append(user)  
                    if users_to_update:  
                        MAIAUser.objects.bulk_update(users_to_update, ["namespace"])  
            
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
            logger.error(f"Error processing user list for group {group_id}: {e}")  
            return {"message": "Error processing user list for group", "status": 400}
    
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
    except IntegrityError as e:
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

        
    # Add the owner to the group
    register_users_in_group_in_keycloak(
        group_id=group_id,
        emails=[user_id],
        settings=settings
    )
    user = MAIAUser.objects.filter(email=user_id).first()
    if user:
        user.namespace = _add_group_to_namespace(user.namespace, group_id)
        user.save()
    
    # Register all users in the group
    users_in_group = get_list_of_users_requesting_a_group(
        group_id=group_id,
        maia_user_model=MAIAUser
    )
    if users_in_group:  
        register_users_in_group_in_keycloak(  
            group_id=group_id,  
            emails=users_in_group,  
            settings=settings
        )
    
    return {"message": "Group already exists in Keycloak" if group_already_exists else "Group created successfully", "status": 200, "group_already_exists": group_already_exists}


def delete_group(group_id):
    """
    Delete a group and remove it from Keycloak.
    
    Args:
        group_id (str): Group identifier (namespace)
        
    Returns:
        dict: Success message or error information
    """
    if not MAIAProject.objects.filter(namespace=group_id).exists():
        return {"message": "Group does not exist", "status": 400}
    MAIAProject.objects.filter(namespace=group_id).delete()
    # Remove all users from the group in Keycloak
    users_in_group = get_list_of_users_requesting_a_group(
        group_id=group_id,
        maia_user_model=MAIAUser
    )
    for user_email in users_in_group:
        remove_user_from_group_in_keycloak(
            email=user_email,
            group_id=group_id,
            settings=settings
        )
    delete_group_in_keycloak(group_id=group_id, settings=settings)
    
    return {"message": "Group deleted successfully", "status": 200}

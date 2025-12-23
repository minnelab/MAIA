import logging
from django.conf import settings
from django.db import IntegrityError
from keycloak.exceptions import KeycloakPostError, KeycloakDeleteError
from apps.models import MAIAUser, MAIAProject
from MAIA.keycloak_utils import (
    register_user_in_keycloak,
    register_group_in_keycloak,
    register_users_in_group_in_keycloak,
    delete_group_in_keycloak,
    remove_user_from_group_in_keycloak,
    get_list_of_users_requesting_a_group,
    get_groups_for_user,
    delete_user_in_keycloak
)
from django.db import transaction

logger = logging.getLogger(__name__)

RESERVED_GROUPS = []
if getattr(settings, "ADMIN_GROUP", None):
    RESERVED_GROUPS.append(settings.ADMIN_GROUP)
if getattr(settings, "USERS_GROUP", None):
    RESERVED_GROUPS.append(settings.USERS_GROUP)

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


def add_user_in_database(email, username, first_name, last_name, namespace):
    """
    Add a new MAIA user to the database.
    """
    user, created = MAIAUser.objects.get_or_create(
        email=email,
        defaults={
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "namespace": namespace,
        },
    )
    return user, created

def update_user_in_database(user, namespace):
    """
    Update a user's namespace/groups in the database.
    """
    if user.namespace != namespace:
        old_namespace = user.namespace
        user.namespace = namespace
        user.save(update_fields=["namespace"])
        logger.info(
            "Updated namespace for existing user '%s' from '%s' to '%s'",
            user.email,
            old_namespace,
            namespace,
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
    # Add user to the database
    user, created = add_user_in_database(email, username, first_name, last_name, namespace)
    if not created:
        update_user_in_database(user, namespace)
    
    # Register user in Keycloak
    try:
        register_user_in_keycloak(email=email, settings=settings)
        user_already_exists = False
    except KeycloakPostError as e:
        logger.error(f"Error registering user {email} in Keycloak: {e}")
        if getattr(e, "response_code", None) == 409:
            user_already_exists = True
        else:
            return {
                "message": "Failed to register user in Keycloak",
                "status": 500,
            }
    
    # Add user to their groups in Keycloak
    if namespace:
        groups = [g.strip() for g in namespace.split(",") if g.strip()]
        for group in groups:
            try:
                register_users_in_group_in_keycloak(
                group_id=group,
                emails=[email],
                settings=settings
            )
            except KeycloakPostError as e:
                if getattr(e, "response_code", None) == 409:
                    logger.warning(f"User was already in group {group} in Keycloak")
                    continue
                else:
                    logger.error(f"Error adding user {email} to group {group} in Keycloak: {e}")
                    return {
                        "message": f"Failed to add user {email} to group {group} in Keycloak: {e}",
                        "status": 500,
                    }
        if user_already_exists:
            groups_in_keycloak = get_groups_for_user(email=email, settings=settings)
            for group in groups_in_keycloak:
                if group not in groups:
                    remove_user_from_group_in_keycloak(
                        email=email,
                        group_id=group,
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
        return {"message": "User does not exist", "status": 404}
    old_namespace = user.namespace

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
        except KeycloakPostError as e:
            if getattr(e, "response_code", None) == 409:
                continue
            else:
                logger.error(
                    f"Error adding user {email} to group {group} in Keycloak during update: {e}"
                )
                return {
                    "message": f"Failed to add user {email} to group {group} in Keycloak during update: {e}",
                    "status": 500,
                }

    # Remove user from groups they are no longer part of in Keycloak
    for group in groups_to_remove:
        try:
            remove_user_from_group_in_keycloak(
                email=email,
                group_id=group,
                settings=settings,
            )
        except KeycloakDeleteError as e:
            if getattr(e, "response_code", None) == 409:
                continue
            else:
                logger.error(
                    f"Error removing user {email} from group {group} in Keycloak during update: {e}"
                )
                return {
                    "message": f"Failed to remove user {email} from group {group} in Keycloak during update: {e}",
                    "status": 500,
                }
    return {"message": "User updated successfully", "status": 200}


def delete_user(email, force=False):
    """
    Delete a user and remove them from all Keycloak groups.
    
    Args:
        email (str): User's email address
        force (bool): Whether to force the deletion of the user from Keycloak. Default is False.
    Returns:
        dict: Success message or error information
    """
    user = MAIAUser.objects.filter(email=email).first()
    if not user:
        return {"message": "User does not exist", "status": 404}
    else:
        namespace = user.namespace
    if namespace:
        groups = [g.strip() for g in namespace.split(",") if g.strip()]
        for group in groups:
            if group not in RESERVED_GROUPS:
                remove_user_from_group_in_keycloak(
                    email=email,
                    group_id=group,
                    settings=settings
                )
            if force:
                if group != settings.ADMIN_GROUP:
                    remove_user_from_group_in_keycloak(
                        email=email,
                        group_id=group,
                        settings=settings
                    )
                    user.namespace = _remove_group_from_namespace(user.namespace, group)
                    user.save(update_fields=["namespace"])
        if not user.is_superuser:
            MAIAUser.objects.filter(email=email).delete()
            if force:
                try:
                    delete_user_in_keycloak(email=email, settings=settings)
                    logger.info(f"User {email} deleted from Keycloak")
                except KeycloakDeleteError as e:
                    if getattr(e, "response_code", None) == 404:
                        logger.warning(f"User {email} does not exist in Keycloak and was not deleted")
                    else:
                        logger.error(f"Error deleting user {email} from Keycloak: {e}")
                        return {
                            "message": f"Error deleting user {email} from Keycloak: {e}",
                            "status": 500,
                        }
        else:
            logger.warning(f"User {email} is a superuser and cannot be deleted")
            return {
                "message": f"User {email} is a superuser and cannot be deleted",
                "status": 403,
            }

    return {"message": "User deleted successfully", "status": 200}


@transaction.atomic
def sync_list_of_users_for_group(group_id, email_list):
    """
    Sync a list of users for a group.

    Args:
        group_id (str): Identifier of the group to synchronize.
        email_list (Iterable[str]): List of user email addresses that should
            be members of the group.
    Returns:
        dict | None: Returns None when synchronization completes
            successfully. If an error occurs while updating users in
            Keycloak, returns a dictionary with "message" and "status" keys
            describing the error.
    """
    # Batch-fetch users to avoid N+1 queries
    users_by_email = {
        user.email: user
        for user in MAIAUser.objects.filter(email__in=email_list)
    }

    users_to_update = []
    emails_to_add_in_keycloak = []

    # Update namespaces in memory and prepare batched Keycloak registration
    for user_email in email_list:
        user = users_by_email.get(user_email)
        if user:
            user.namespace = _add_group_to_namespace(user.namespace, group_id)
            users_to_update.append(user)
            emails_to_add_in_keycloak.append(user_email)

    if users_to_update:
        MAIAUser.objects.bulk_update(users_to_update, ["namespace"])

    if emails_to_add_in_keycloak:
        try:
            register_users_in_group_in_keycloak(
                group_id=group_id,
                emails=emails_to_add_in_keycloak,
                settings=settings,
            )
        except KeycloakPostError as e:
            if getattr(e, "response_code", None) == 409:
                logger.warning(f"One or more users already exists in group {group_id}")
                # 409 means "already exists", so we mark it as success and proceed
            elif getattr(e, "response_code", None) == 404:
                logger.warning(f"One or more users do not exist in the database and were not added to group {group_id}")
                return {
                    "message": f"One or more users do not exist in the database and were not added to group {group_id}",
                    "status": 404,
                }
            else:
                logger.error(f"Error processing user list for group {group_id}: {e}")
                return {
                    "message": f"Error processing user list for group {group_id}: {e}",
                    "status": 500,
                }
        if settings.ADMIN_GROUP and group_id == settings.ADMIN_GROUP:
            logger.info(f"Updating admin group, adding users to admin group")
            for user_email in emails_to_add_in_keycloak:
                logger.info(f"Adding user {user_email} to admin group")
                user = MAIAUser.objects.filter(email=user_email).first()
                if user:
                    user.is_superuser = True
                    user.is_staff = True
                    user.save(update_fields=["is_superuser", "is_staff"])

    # Remove users not in the new list
    registered_users = get_list_of_users_requesting_a_group(
        group_id=group_id,
        maia_user_model=MAIAUser
    )
    if len(registered_users) > 0:
        emails_to_remove = [
            user_email for user_email in registered_users
            if user_email not in email_list
        ]
        if emails_to_remove:
            users_to_update = []
            for user in MAIAUser.objects.filter(email__in=emails_to_remove):
                user.namespace = _remove_group_from_namespace(user.namespace, group_id)
                users_to_update.append(user)
            if users_to_update:
                MAIAUser.objects.bulk_update(users_to_update, ["namespace"])
            
            if settings.ADMIN_GROUP and group_id == settings.ADMIN_GROUP:
                logger.info(f"Updating admin group, removing users from admin group")
                admin_users_qs = MAIAUser.objects.filter(email__in=emails_to_remove)
                admin_users_to_update = list(admin_users_qs)
                for user in admin_users_to_update:
                    logger.info(f"Removing user {user.email} from admin group")
                if admin_users_to_update:
                    admin_users_qs.update(is_superuser=False, is_staff=False)
    
        # Clean up Keycloak groups
        for user_email in emails_to_remove:
            try:
                remove_user_from_group_in_keycloak(
                    email=user_email,
                    group_id=group_id,
                    settings=settings,
                )
            except KeycloakDeleteError as e:
                if getattr(e, "response_code", None) == 409:
                    logger.warning(f"User was already not in group {group_id}")
                    # Already not in group, so continue
                    continue
                elif getattr(e, "response_code", None) == 404:
                    logger.warning(f"User does not exist in Keycloak and could not be removed from group {group_id}")
                    continue
                else:
                    logger.error(f"Error removing user from group {group_id}: {e}")
                    return {
                        "message": f"Error removing user from group {group_id}: {e}",
                        "status": 500,
                    }
    
    return {"message": "List of users synchronized successfully", "status": 200}


def create_group(group_id, gpu, date, memory_limit, cpu_limit, conda, cluster, minimal_env, user_id, email_list=None):
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
        email_list (list, optional): List of user emails to add to the group
        
    Returns:
        dict: Success message or error information
    """
    if email_list is not None and not isinstance(email_list, list):
        return {"message": "User list must be a list", "status": 400}
    try:
        register_group_in_keycloak(group_id=group_id, settings=settings)
        group_already_exists = False
    except KeycloakPostError as e:
        if getattr(e, "response_code", None) == 409:
            group_already_exists = True
            logger.warning(f"Group {group_id} already exists in Keycloak")
        else:
            logger.error(f"Error registering group {group_id} in Keycloak: {e}")
            return {
                "message": f"Failed to register group {group_id} in Keycloak: {e}",
                "status": 500,
            }

    if not email_list:
        email_list = [user_id]
    else:
        email_list = [user_id] + email_list
    sync_result = sync_list_of_users_for_group(group_id, email_list)
    
    if isinstance(sync_result, dict):
        status = sync_result.get("status")
        if status is not None and status != 200:
            return sync_result
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
    
    return {"message": "Group already exists in Keycloak" if group_already_exists else "Group created successfully", "status": 200, "group_already_exists": group_already_exists}

@transaction.atomic
def delete_group(group_id):
    """
    Delete a group and remove it from Keycloak.
    
    Args:
        group_id (str): Group identifier (namespace)
        
    Returns:
        dict: Success message or error information
    """
    if group_id in RESERVED_GROUPS:
        return {"message": "Group is a reserved group and cannot be deleted", "status": 403}
    if not MAIAProject.objects.filter(namespace=group_id).exists():
        return {"message": "Group does not exist", "status": 400}
    MAIAProject.objects.filter(namespace=group_id).delete()
    # Remove all users from the group in Keycloak
    users_in_group = get_list_of_users_requesting_a_group(
        group_id=group_id,
        maia_user_model=MAIAUser
    )
    for user_email in users_in_group:
        try:
            remove_user_from_group_in_keycloak(
                email=user_email,
                group_id=group_id,
                settings=settings
            )
        except KeycloakDeleteError as e:
            if getattr(e, "response_code", None) == 409:
                logger.warning(f"User was already not in group {group_id} in Keycloak")
                continue
            elif getattr(e, "response_code", None) == 404:
                logger.warning(f"User does not exist in Keycloak and could not be removed from group {group_id}")
                continue
            else:
                logger.error(f"Error removing user from group {group_id} in Keycloak: {e}")
                return {
                    "message": f"Error removing user from group {group_id} in Keycloak: {e}",
                    "status": 500,
                }
    try:
        delete_group_in_keycloak(group_id=group_id, settings=settings)
    except KeycloakDeleteError as e:
        if getattr(e, "response_code", None) == 404:
            logger.warning(f"Group does not exist in Keycloak and could not be deleted")
            return {
                "message": f"Group does not exist in Keycloak and could not be deleted",
                "status": 404,
            }
    
    return {"message": "Group deleted successfully", "status": 200}

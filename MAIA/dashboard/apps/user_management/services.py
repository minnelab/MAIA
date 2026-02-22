
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
    delete_user_in_keycloak,
)
from django.db import transaction
from loguru import logger

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
    with transaction.atomic():
        user, created = add_user_in_database(email, username, first_name, last_name, namespace)
        if not created:
            update_user_in_database(user, namespace)

        # Register user in Keycloak
        try:
            register_user_in_keycloak(email=email, settings=settings)
            user_already_exists = False
        except KeycloakPostError as e:
            logger.error(f"Error registering user {email} in Keycloak: {e}")
            if getattr(e, "response_code", 0) == 409:
                user_already_exists = True
            else:
                transaction.set_rollback(True)
                raise

        # Add user to their groups in Keycloak
        if namespace:
            groups = [g.strip() for g in namespace.split(",") if g.strip()]
            for group in groups:
                try:
                    register_users_in_group_in_keycloak(group_id=group, emails=[email], settings=settings)
                except KeycloakPostError as e:
                    if getattr(e, "response_code", 0) == 409:
                        logger.warning(f"User was already in group {group} in Keycloak")
                        continue
                    else:
                        logger.error(f"Error adding user {email} to group {group} in Keycloak.")
                        transaction.set_rollback(True)
                        raise
            if user_already_exists:
                groups_in_keycloak = get_groups_for_user(email=email, settings=settings)
                for group in groups_in_keycloak:
                    if group not in groups:
                        try:
                            remove_user_from_group_in_keycloak(email=email, group_id=group, settings=settings)
                        except KeycloakDeleteError as e:
                            if getattr(e, "response_code", 0) == 409:
                                logger.warning(f"User was already not in group {group} in Keycloak")
                            else:
                                logger.error(f"Error removing user {email} from group {group} in Keycloak.")
                                transaction.set_rollback(True)
                                raise
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
    with transaction.atomic():
        try:
            # Lock the user row to prevent concurrent modifications/deletion
            user = MAIAUser.objects.select_for_update().get(email=email)
        except MAIAUser.DoesNotExist:
            # If user does not exist in the database, there is nothing to sync in Keycloak
            return {"message": "User does not exist", "status": 404}
        old_namespace = user.namespace
        # Update namespace in the MAIA database using the locked instance
        user.namespace = namespace
        user.save(update_fields=["namespace"])

        # Normalize namespaces to sets of group IDs
        old_groups = {g.strip() for g in (old_namespace or "").split(",") if g.strip()}
        new_groups = {g.strip() for g in (namespace or "").split(",") if g.strip()}

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
                if getattr(e, "response_code", 0) == 409:
                    continue
                else:
                    logger.error(f"Error adding user {email} to group {group} in Keycloak during update.")
                    transaction.set_rollback(True)
                    raise

        # Remove user from groups they are no longer part of in Keycloak
        for group in groups_to_remove:
            try:
                remove_user_from_group_in_keycloak(
                    email=email,
                    group_id=group,
                    settings=settings,
                )
            except KeycloakDeleteError as e:
                if getattr(e, "response_code", 0) == 409:
                    continue
                else:
                    logger.error(f"Error removing user {email} from group {group} in Keycloak during update.")
                    transaction.set_rollback(True)
                    raise
    return {"message": "User updated successfully", "status": 200}

@transaction.atomic
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
    if user and user.is_superuser:
        logger.error(f"User {email} is a superuser and cannot be deleted")
        return {"message": "User is a superuser and cannot be deleted", "status": 500}
    if not user:
        return {"message": "User does not exist", "status": 404}
    else:
        namespace = user.namespace
    if namespace:
        groups = [g.strip() for g in namespace.split(",") if g.strip()]
        for group in groups:
            if group not in RESERVED_GROUPS:
                try:
                    remove_user_from_group_in_keycloak(email=email, group_id=group, settings=settings)
                except KeycloakDeleteError as e:
                    if getattr(e, "response_code", 0) == 404:
                        logger.warning(f"User {email} is not a member of group {group} in Keycloak and could not be removed")
                    else:
                        logger.error(f"Error removing user {email} from group {group} in Keycloak.")
                        raise
    MAIAUser.objects.filter(email=email).delete()
    if force:
        try:
            delete_user_in_keycloak(email=email, settings=settings)
            logger.info(f"User {email} deleted from Keycloak")
        except KeycloakDeleteError as e:
            if getattr(e, "response_code", 0) == 404:
                logger.warning(f"User {email} does not exist in Keycloak and was not deleted")
            else:
                logger.error(f"Error deleting user {email} from Keycloak.")
                raise
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
        dict: A dictionary with "message" and "status" keys describing the
            result of the synchronization, including any errors encountered
            while updating users in Keycloak.
    """
    if not email_list:
        email_list = []
    # Batch-fetch users to avoid N+1 queries
    users_by_email = {user.email: user for user in MAIAUser.objects.filter(email__in=email_list)}

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
            if getattr(e, "response_code", 0) == 409:
                logger.warning(f"One or more users already exists in group {group_id}")
                # 409 means "already exists", so we mark it as success and proceed
            elif getattr(e, "response_code", 0) == 404:
                logger.warning(f"One or more users do not exist in the database and were not added to group {group_id}")
                raise
            else:
                logger.error(f"Error processing user list for group {group_id}.")
                raise
    if getattr(settings, "ADMIN_GROUP", None) and group_id == getattr(settings, "ADMIN_GROUP", None):
        logger.info("Updating admin group, adding users to admin group")
        # Bulk update: Set is_superuser and is_staff for all admin users being added
        admin_users_qs = MAIAUser.objects.filter(email__in=emails_to_add_in_keycloak)
        admin_users_to_update = list(admin_users_qs)
        for user in admin_users_to_update:
            logger.info(f"Adding user {user.email} to admin group")
            user.is_superuser = True
            user.is_staff = True
        if admin_users_to_update:
            MAIAUser.objects.bulk_update(admin_users_to_update, ["is_superuser", "is_staff"])

    # Remove users not in the new list
    registered_users = get_list_of_users_requesting_a_group(group_id=group_id, maia_user_model=MAIAUser)
    if len(registered_users) > 0:
        emails_to_remove = [user_email for user_email in registered_users if user_email not in email_list]
        if emails_to_remove:
            users_to_update = []
            for user in MAIAUser.objects.filter(email__in=emails_to_remove):
                user.namespace = _remove_group_from_namespace(user.namespace, group_id)
                users_to_update.append(user)
            if users_to_update:
                MAIAUser.objects.bulk_update(users_to_update, ["namespace"])

            if getattr(settings, "ADMIN_GROUP", None) and group_id == getattr(settings, "ADMIN_GROUP", None):
                logger.info("Updating admin group, removing users from admin group")
                admin_users_qs = MAIAUser.objects.filter(email__in=emails_to_remove)
                admin_users_to_update = list(admin_users_qs)
                for user in admin_users_to_update:
                    logger.info(f"Removing user {user.email} from admin group")
                    user.is_superuser = False
                    user.is_staff = False
                if admin_users_to_update:
                    MAIAUser.objects.bulk_update(admin_users_to_update, ["is_superuser", "is_staff"])

        # Clean up Keycloak groups
        for user_email in emails_to_remove:
            try:
                remove_user_from_group_in_keycloak(
                    email=user_email,
                    group_id=group_id,
                    settings=settings,
                )
            except KeycloakDeleteError as e:
                if getattr(e, "response_code", 0) == 409:
                    logger.warning(f"User was already not in group {group_id}")
                    # Already not in group, so continue
                    continue
                elif getattr(e, "response_code", 0) == 404:
                    logger.warning(f"User does not exist in Keycloak and could not be removed from group {group_id}")
                    continue
                else:
                    logger.error(f"Error removing user from group {group_id}.")
                    raise

    return {"message": "List of users synchronized successfully", "status": 200}


@transaction.atomic
def create_group(group_id, gpu, date, memory_limit, cpu_limit, conda, cluster, minimal_env, user_email, email_list=None, description=None, supervisor=None):
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
        user_email (str): Email of the user creating/owning the group
        email_list (list, optional): List of user emails to add to the group
        description (str, optional): Project description
        supervisor (str, optional): Supervisor email for student projects

    Returns:
        dict: Success message or error information
    """
    if email_list is not None and not isinstance(email_list, list):
        return {"message": "User list must be a list", "status": 400}
    try:
        register_group_in_keycloak(group_id=group_id, settings=settings)
        group_already_exists = False
    except KeycloakPostError as e:
        if getattr(e, "response_code", 0) == 409:
            group_already_exists = True
            logger.warning(f"Group {group_id} already exists in Keycloak")
        else:
            logger.error(f"Error registering group {group_id} in Keycloak.")
            raise

    if user_email and MAIAUser.objects.filter(email=user_email).exists():
        if not email_list:
            email_list = [user_email]
        else:
            email_list = [user_email] + email_list
    if supervisor and MAIAUser.objects.filter(email=supervisor).exists():
        if not email_list:
            email_list = [supervisor]
        else:
            email_list = [supervisor] + email_list
        user_email = supervisor
    sync_result = sync_list_of_users_for_group(group_id, email_list)

    if isinstance(sync_result, dict):
        status = sync_result.get("status")
        if status is not None and status != 200:
            raise RuntimeError(
                f"Failed to sync users for group {group_id}: {sync_result}"
            )
    # Create or update the project
    try:
        MAIAProject.objects.create(
            namespace=group_id,
            email=user_email,
            gpu=gpu,
            date=date,
            memory_limit=memory_limit,
            cpu_limit=cpu_limit,
            conda=conda,
            cluster=cluster,
            minimal_env=minimal_env,
            description=description,
            supervisor=supervisor,
        )
    except IntegrityError:
        logger.warning(f"Group {group_id} already exists in the database")


    return {
        "message": "Group already exists in Keycloak" if group_already_exists else "Group created successfully",
        "status": 200,
        "group_already_exists": group_already_exists,
    }


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
    # Remove all users from the group in Keycloak
    users_in_group = get_list_of_users_requesting_a_group(group_id=group_id, maia_user_model=MAIAUser)
    for user_email in users_in_group:
        maia_users = MAIAUser.objects.filter(email=user_email)
        try:
            remove_user_from_group_in_keycloak(email=user_email, group_id=group_id, settings=settings)
        except KeycloakDeleteError as e:
            if getattr(e, "response_code", 0) == 409:
                logger.warning(f"User was already not in group {group_id} in Keycloak")
                # Even if the user was already not in the group in Keycloak,
                # ensure the namespace field in MAIAUser is updated.
                for maia_user in maia_users:
                    maia_user.namespace = _remove_group_from_namespace(maia_user.namespace, group_id)
                MAIAUser.objects.bulk_update(maia_users, ["namespace"])
                continue
            elif getattr(e, "response_code", 0) == 404:
                logger.warning(f"User does not exist in Keycloak and could not be removed from group {group_id}")
                # If the user does not exist in Keycloak, still remove the group
                # from the namespace field in MAIAUser.
                for maia_user in maia_users:
                    maia_user.namespace = _remove_group_from_namespace(maia_user.namespace, group_id)
                MAIAUser.objects.bulk_update(maia_users, ["namespace"])
                continue
            else:
                logger.error(f"Error removing user from group {group_id} in Keycloak.")
                raise
        # On successful removal from the group in Keycloak, also update the
        # namespace field in MAIAUser to remove the group.
        for maia_user in maia_users:
            maia_user.namespace = _remove_group_from_namespace(maia_user.namespace, group_id)
        MAIAUser.objects.bulk_update(maia_users, ["namespace"])
    try:
        delete_group_in_keycloak(group_id=group_id, settings=settings)
    except KeycloakDeleteError as e:
        if getattr(e, "response_code", 0) == 404:
            logger.warning("Group does not exist in Keycloak and could not be deleted")
        else:
            logger.error(f"Error deleting group {group_id} in Keycloak.")
            raise
    MAIAProject.objects.filter(namespace=group_id).delete()
    return {"message": "Group deleted successfully", "status": 200}

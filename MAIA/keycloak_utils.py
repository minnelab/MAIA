from __future__ import annotations

import os

from keycloak import KeycloakAdmin, KeycloakOpenIDConnection


def get_user_ids(settings):
    """
    Retrieve user IDs and their associated MAIA groups from Keycloak.

    Parameters
    ----------
    settings : object
        An object containing the Keycloak server settings. It should have the following attributes:
        - OIDC_SERVER_URL: str, the URL of the Keycloak server.
        - OIDC_USERNAME: str, the username for Keycloak authentication.
        - OIDC_REALM_NAME: str, the realm name in Keycloak.
        - OIDC_RP_CLIENT_ID: str, the client ID for Keycloak.
        - OIDC_RP_CLIENT_SECRET: str, the client secret for Keycloak.

    Returns
    -------
    dict
        A dictionary where the keys are user email addresses and the values are lists of MAIA groups the user belongs to.
    """

    keycloak_connection = KeycloakOpenIDConnection(
        server_url=settings.OIDC_SERVER_URL,
        username=settings.OIDC_USERNAME,
        password="",
        realm_name=settings.OIDC_REALM_NAME,
        client_id=settings.OIDC_RP_CLIENT_ID,
        client_secret_key=settings.OIDC_RP_CLIENT_SECRET,
        verify=False,
    )

    keycloak_admin = KeycloakAdmin(connection=keycloak_connection)

    users = keycloak_admin.get_users()

    user_list = {}
    groups = keycloak_admin.get_groups()
    maia_groups = {group["id"]: group["name"][len("MAIA:") :] for group in groups if group["name"].startswith("MAIA:")}

    for maia_group in maia_groups:

        users = keycloak_admin.get_group_members(group_id=maia_group)
        emails = [user["email"] for user in users if "email" in user]
        for email in emails:
            if email in user_list:
                user_list[email] += [maia_groups[maia_group]]
            else:
                user_list[email] = [maia_groups[maia_group]]

    return user_list


def get_groups_for_user(email, settings):
    """
    Retrieve the MAIA groups associated with a user in Keycloak.

    Parameters
    ----------
    email : str
        The email address of the user to retrieve groups for.
    settings : object
        An object containing the Keycloak server settings. It should have the following attributes:
        - OIDC_SERVER_URL: str, the URL of the Keycloak server.
        - OIDC_USERNAME: str, the username for Keycloak authentication.
        - OIDC_REALM_NAME: str, the realm name in Keycloak.
        - OIDC_RP_CLIENT_ID: str, the client ID for Keycloak.
        - OIDC_RP_CLIENT_SECRET: str, the client secret for Keycloak.

    Returns
    -------
    list
        A list of MAIA groups that the user is associated with.
    """

    keycloak_connection = KeycloakOpenIDConnection(
        server_url=settings.OIDC_SERVER_URL,
        username=settings.OIDC_USERNAME,
        password="",
        realm_name=settings.OIDC_REALM_NAME,
        client_id=settings.OIDC_RP_CLIENT_ID,
        client_secret_key=settings.OIDC_RP_CLIENT_SECRET,
        verify=False,
    )
    keycloak_admin = KeycloakAdmin(connection=keycloak_connection)
    groups = keycloak_admin.get_groups()
    maia_groups = {group["id"]: group["name"][len("MAIA:") :] for group in groups if group["name"].startswith("MAIA:")}

    user_groups = []
    for maia_group in maia_groups:
        users = keycloak_admin.get_group_members(group_id=maia_group)
        for user in users:
            if "email" in user and user["email"] == email:
                user_groups.append(maia_groups[maia_group])

    return user_groups


def remove_user_from_group_in_keycloak(email, group_id, settings):
    """
    Remove a user from a group in Keycloak.

    Parameters
    ----------
    email : str
        The email address of the user to be removed from the group.
    group_id : str
        The ID of the group from which the user should be removed.
    settings : object
        An object containing the Keycloak server settings. It should have the following attributes:
        - OIDC_SERVER_URL: str, the URL of the Keycloak server.
        - OIDC_USERNAME: str, the username for Keycloak authentication.
        - OIDC_REALM_NAME: str, the realm name in Keycloak.
        - OIDC_RP_CLIENT_ID: str, the client ID for Keycloak.
        - OIDC_RP_CLIENT_SECRET: str, the client secret for Keycloak.

    Returns
    -------
    None
    """

    keycloak_connection = KeycloakOpenIDConnection(
        server_url=settings.OIDC_SERVER_URL,
        username=settings.OIDC_USERNAME,
        password="",
        realm_name=settings.OIDC_REALM_NAME,
        client_id=settings.OIDC_RP_CLIENT_ID,
        client_secret_key=settings.OIDC_RP_CLIENT_SECRET,
        verify=False,
    )
    keycloak_admin = KeycloakAdmin(connection=keycloak_connection)
    groups = keycloak_admin.get_groups()
    maia_groups = {group["id"]: group["name"][len("MAIA:") :] for group in groups if group["name"].startswith("MAIA:")}

    for maia_group in maia_groups:
        if maia_groups[maia_group] in [group_id]:
            users = keycloak_admin.get_group_members(group_id=maia_group)
            for user in users:
                if "email" in user and user["email"] == email:
                    keycloak_admin.group_user_remove(user["id"], maia_group)

    return None


def delete_group_in_keycloak(group_id, settings):
    """
    Delete a group in Keycloak

    Parameters
    ----------
    group_id : str
        The ID of the group to be deleted.
    settings : object
        An object containing the Keycloak server settings. It should have the following attributes:
        - OIDC_SERVER_URL: str, the URL of the Keycloak server.
        - OIDC_USERNAME: str, the username for Keycloak authentication.
        - OIDC_REALM_NAME: str, the realm name in Keycloak.
        - OIDC_RP_CLIENT_ID: str, the client ID for Keycloak.
        - OIDC_RP_CLIENT_SECRET: str, the client secret for Keycloak.

    Returns
    -------
    None
    """

    keycloak_connection = KeycloakOpenIDConnection(
        server_url=settings.OIDC_SERVER_URL,
        username=settings.OIDC_USERNAME,
        password="",
        realm_name=settings.OIDC_REALM_NAME,
        client_id=settings.OIDC_RP_CLIENT_ID,
        client_secret_key=settings.OIDC_RP_CLIENT_SECRET,
        verify=False,
    )
    keycloak_admin = KeycloakAdmin(connection=keycloak_connection)
    groups = keycloak_admin.get_groups()
    maia_groups = {group["id"]: group["name"][len("MAIA:") :] for group in groups if group["name"].startswith("MAIA:")}

    for maia_group in maia_groups:
        if maia_groups[maia_group] in [group_id]:
            keycloak_admin.delete_group(group_id=maia_group)

    return None


def get_groups_in_keycloak(settings):
    """
    Retrieve groups from Keycloak that start with "MAIA:" and return them in a dictionary.

    Parameters
    ----------
    settings : object
    An object containing the Keycloak connection settings.
    It should have the following attributes:
    - OIDC_SERVER_URL : str
        The URL of the Keycloak server.
    - OIDC_USERNAME : str
        The username for Keycloak authentication.
    - OIDC_REALM_NAME : str
        The name of the Keycloak realm.
    - OIDC_RP_CLIENT_ID : str
        The client ID for Keycloak.
    - OIDC_RP_CLIENT_SECRET : str
        The client secret for Keycloak.

    Returns
    -------
    dict
        A dictionary where the keys are group IDs and the values are group names
        (with the "MAIA:" prefix removed) for groups that start with "MAIA:".
    """
    keycloak_connection = KeycloakOpenIDConnection(
        server_url=settings.OIDC_SERVER_URL,
        username=settings.OIDC_USERNAME,
        password="",
        realm_name=settings.OIDC_REALM_NAME,
        client_id=settings.OIDC_RP_CLIENT_ID,
        client_secret_key=settings.OIDC_RP_CLIENT_SECRET,
        verify=False,
    )

    keycloak_admin = KeycloakAdmin(connection=keycloak_connection)

    groups = keycloak_admin.get_groups()

    maia_groups = {group["id"]: group["name"][len("MAIA:") :] for group in groups if group["name"].startswith("MAIA:")}

    return maia_groups


def register_user_in_keycloak(email, settings):
    """
    Registers a user in Keycloak and sends an approved registration email.

    Parameters
    ----------
    email : str
        The email address of the user to be registered.
    settings : object
        An object containing the necessary settings for Keycloak connection and email sending.

    Settings Attributes
    -------------------
    OIDC_SERVER_URL : str
        The URL of the Keycloak server.
    OIDC_USERNAME : str
        The username for Keycloak authentication.
    OIDC_REALM_NAME : str
        The name of the Keycloak realm.
    OIDC_RP_CLIENT_ID : str
        The client ID for Keycloak.
    OIDC_RP_CLIENT_SECRET : str
        The client secret for Keycloak.
    HOSTNAME : str
        The hostname for generating the MAIA login URL.

    Returns
    -------
    None
    """
    keycloak_connection = KeycloakOpenIDConnection(
        server_url=settings.OIDC_SERVER_URL,
        username=settings.OIDC_USERNAME,
        password="",
        realm_name=settings.OIDC_REALM_NAME,
        client_id=settings.OIDC_RP_CLIENT_ID,
        client_secret_key=settings.OIDC_RP_CLIENT_SECRET,
        verify=False,
    )

    keycloak_admin = KeycloakAdmin(connection=keycloak_connection)

    temp_password = "Maia4YOU!"

    keycloak_admin.create_user(
        {
            "username": email,
            "email": email,
            "emailVerified": True,
            "enabled": True,
            # 'firstName':'Demo2',
            # 'lastName':'Maia',
            "requiredActions": ["UPDATE_PASSWORD"],
            "credentials": [{"type": "password", "temporary": True, "value": temp_password}],
        }
    )
    maia_login_url = "https://" + settings.HOSTNAME + "/maia/"
    if "email_account" in os.environ and "email_password" in os.environ and "email_smtp_server" in os.environ:
        from MAIA.dashboard_utils import send_approved_registration_email

        send_approved_registration_email(email, maia_login_url, temp_password)


def register_group_in_keycloak(group_id, settings):
    """
    Registers a group in Keycloak with the specified group ID and settings.

    Parameters
    ----------
    group_id : str
        The ID of the group to be registered.
    settings : object
    An object containing the Keycloak server settings, including:
    - OIDC_SERVER_URL : str
        The URL of the Keycloak server.
    - OIDC_USERNAME : str
        The username for Keycloak authentication.
    - OIDC_REALM_NAME : str
        The name of the Keycloak realm.
    - OIDC_RP_CLIENT_ID : str
        The client ID for Keycloak.
    - OIDC_RP_CLIENT_SECRET : str
        The client secret for Keycloak.

    Returns
    -------
    None
    """
    keycloak_connection = KeycloakOpenIDConnection(
        server_url=settings.OIDC_SERVER_URL,
        username=settings.OIDC_USERNAME,
        password="",
        realm_name=settings.OIDC_REALM_NAME,
        client_id=settings.OIDC_RP_CLIENT_ID,
        client_secret_key=settings.OIDC_RP_CLIENT_SECRET,
        verify=False,
    )

    keycloak_admin = KeycloakAdmin(connection=keycloak_connection)

    payload = {
        "name": f"MAIA:{group_id}",
        "path": f"/MAIA:{group_id}",
        "attributes": {},
        "realmRoles": [],
        "clientRoles": {},
        "subGroups": [],
        "access": {"view": True, "manage": True, "manageMembership": True},
    }
    keycloak_admin.create_group(payload)


def register_users_in_group_in_keycloak(emails, group_id, settings):
    """
    Registers users in a specified Keycloak group.

    Parameters
    ----------
    emails : list
        A list of email addresses of users to be added to the group.
    group_id : str
        The ID of the group to which users should be added.
    settings : object
    An object containing Keycloak server settings, including:
    - OIDC_SERVER_URL : str
        The URL of the Keycloak server.
    - OIDC_USERNAME : str
        The username for Keycloak authentication.
    - OIDC_REALM_NAME : str
        The realm name in Keycloak.
    - OIDC_RP_CLIENT_ID : str
        The client ID for Keycloak.
    - OIDC_RP_CLIENT_SECRET : str
        The client secret for Keycloak.

    Returns
    -------
    None
    """
    keycloak_connection = KeycloakOpenIDConnection(
        server_url=settings.OIDC_SERVER_URL,
        username=settings.OIDC_USERNAME,
        password="",
        realm_name=settings.OIDC_REALM_NAME,
        client_id=settings.OIDC_RP_CLIENT_ID,
        client_secret_key=settings.OIDC_RP_CLIENT_SECRET,
        verify=False,
    )

    keycloak_admin = KeycloakAdmin(connection=keycloak_connection)

    groups = keycloak_admin.get_groups()

    users = keycloak_admin.get_users()
    for user in users:
        if "email" in user and user["email"] in emails:
            uid = user["id"]
            for group in groups:
                if group["name"] == "MAIA:" + group_id:
                    gid = group["id"]
                    keycloak_admin.group_user_add(uid, gid)
                elif group["name"] == "MAIA:users":
                    try:
                        gid = group["id"]
                        keycloak_admin.group_user_add(uid, gid)
                    except Exception:
                        ...


def get_list_of_groups_requesting_a_user(email, user_model):
    """
    Retrieves a list of groups (namespaces) that have requested a specific user based on their email.

    Parameters
    ----------
    email : str
        The email address of the user to search for.
    user_model : object
        The user model object to query for user information.

    Returns
    -------
    list
        A list of namespaces that have requested the user. Returns an empty list if no groups are found.

    Raises
    ------
    KeyError
        If environment variables 'DB_HOST', 'DB_USERNAME', or 'DB_PASS' are not set in non-debug mode.
    Exception
        If there is an issue connecting to the database or executing the SQL queries.
    """

    try:
        return user_model.objects.filter(email=email).first().namespace.split(",")
    except AttributeError:
        return []


def get_list_of_users_requesting_a_group(maia_user_model, group_id):
    """
    Retrieves a list of email addresses of users who have requested access to a specific group.

    Parameters
    ----------
    group_id : str
        The ID of the group to check for user requests.
    settings : object
        A settings object that contains configuration parameters, including DEBUG and LOCAL_DB_PATH.

    Returns
    -------
    list
        A list of email addresses of users who have requested access to the specified group.

    Raises
    ------
    KeyError
        If environment variables for database connection are not set when DEBUG is False.
    Exception
        If there is an issue with database connection or query execution.

    Notes
    -----
    When settings.DEBUG is True, a local SQLite database is used.
    When settings.DEBUG is False, a MySQL database is used with connection parameters from environment variables.
    """

    users = []
    for user in maia_user_model.objects.all():
        requested_namespaces = user.namespace.split(",")
        if group_id in requested_namespaces:
            users.append(user.email)

    return users


def get_maia_users_from_keycloak(settings):
    """
    Retrieves all users from Keycloak who are members of any MAIA group.

    Parameters
    ----------
    settings : object
    An object containing Keycloak connection settings, including:
    - OIDC_SERVER_URL : str
        The URL of the Keycloak server.
    - OIDC_USERNAME : str
        The username for Keycloak authentication.
    - OIDC_REALM_NAME : str
        The realm name in Keycloak.
    - OIDC_RP_CLIENT_ID : str
        The client ID for Keycloak.
    - OIDC_RP_CLIENT_SECRET : str
        The client secret for Keycloak.

    Returns
    -------
    list
        A list of dictionaries containing user information for all users in MAIA groups.
        Each dictionary contains user details like email, username, and groups.
    """
    keycloak_connection = KeycloakOpenIDConnection(
        server_url=settings.OIDC_SERVER_URL,
        username=settings.OIDC_USERNAME,
        password="",
        realm_name=settings.OIDC_REALM_NAME,
        client_id=settings.OIDC_RP_CLIENT_ID,
        client_secret_key=settings.OIDC_RP_CLIENT_SECRET,
        verify=False,
    )

    keycloak_admin = KeycloakAdmin(connection=keycloak_connection)

    # Get all groups that start with "MAIA:"
    # groups = keycloak_admin.get_groups()
    # maia_groups = {group["id"]: group["name"] for group in groups if group["name"].startswith("MAIA:")}

    # Get all users and filter those who are in MAIA groups
    maia_users = []
    all_users = keycloak_admin.get_users()

    for user in all_users:
        if "email" not in user:
            continue

        user_groups = keycloak_admin.get_user_groups(user_id=user["id"])
        user_maia_groups = [group["name"] for group in user_groups if group["name"].startswith("MAIA:")]

        if user_maia_groups:
            maia_users.append(
                {"email": user["email"], "username": user["username"], "id": user["id"], "groups": user_maia_groups}
            )

    return maia_users

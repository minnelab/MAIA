#! /usr/bin/env python3
from keycloak import KeycloakAdmin
from keycloak import KeycloakOpenIDConnection
import argparse
from argparse import RawTextHelpFormatter
from textwrap import dedent
from pathlib import Path

from loguru import logger

EPILOG = dedent(
    """
    Example call:
    ::
        {filename} --client_secret <client_secret> --server_url <server_url>
    """.format(  # noqa: E501
        filename=Path(__file__).stem
    )
)


def create_admin_user_and_group(
    server_url: str, client_secret: str, admin_email="admin@maia.se", group_id="users", admin_password="Admin"
):
    keycloak_connection = KeycloakOpenIDConnection(
        server_url=server_url,
        username="user",
        password="",
        realm_name="maia",
        client_id="maia",
        client_secret_key=client_secret,
        verify=False,
    )

    keycloak_admin = KeycloakAdmin(connection=keycloak_connection)

    try:
        keycloak_admin.create_user(
            {
                "username": admin_email,
                "email": admin_email,
                "emailVerified": True,
                "enabled": True,
                "firstName": "Admin",
                "lastName": "Maia",
                "requiredActions": ["UPDATE_PASSWORD"],
                "credentials": [{"type": "password", "temporary": True, "value": admin_password}],
            }
        )
    except Exception as e:
        logger.error(f"Error creating admin user: {e}")
        pass

    payload = {
        "name": f"MAIA:{group_id}",
        "path": f"/MAIA:{group_id}",
        "attributes": {},
        "realmRoles": [],
        "clientRoles": {},
        "subGroups": [],
        "access": {"view": True, "manage": True, "manageMembership": True},
    }
    try:
        keycloak_admin.create_group(payload)
    except Exception as e:
        logger.error(f"Error creating group: {e}")
        pass

    groups = keycloak_admin.get_groups()

    users = keycloak_admin.get_users()
    for user in users:
        if "email" in user and user["email"] in [admin_email]:
            uid = user["id"]
            for group in groups:
                if group["name"] == f"MAIA:{group_id}":
                    gid = group["id"]
                    keycloak_admin.group_user_add(uid, gid)

    client_uuid = keycloak_admin.get_client_id("realm-management")
    client_roles = keycloak_admin.get_client_roles(client_uuid)
    for group in groups:
        if group["name"] == "MAIA:admin":
            gid = group["id"]
            keycloak_admin.assign_group_client_roles(
                group_id=gid,
                client_id=client_uuid,
                roles=client_roles,
            )


def get_arg_parser():
    parser = argparse.ArgumentParser(
        description="Configure Keycloak",
        epilog=EPILOG,
        formatter_class=RawTextHelpFormatter,
    )
    parser.add_argument("--client_secret", type=str, required=True, help="The client secret to use")
    parser.add_argument("--server_url", type=str, required=True, help="The server URL to configure")
    return parser


def main():
    args = get_arg_parser().parse_args()
    create_admin_user_and_group(args.server_url, args.client_secret)


if __name__ == "__main__":
    main()

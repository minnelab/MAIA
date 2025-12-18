#! /usr/bin/env python3
from keycloak import KeycloakAdmin
from keycloak import KeycloakOpenIDConnection
import json
import argparse
from argparse import RawTextHelpFormatter
from textwrap import dedent
from pathlib import Path

EPILOG = dedent(
    """
    Example call:
    ::
        {filename} --client_secret <client_secret> --realm_file <realm_file>
    """.format(  # noqa: E501
        filename=Path(__file__).stem
    )
)


def create_admin_user_and_group(server_url: str, client_secret: str):
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

    keycloak_admin.create_user(
        {
            "username": "admin@maia.se",
            "email": "admin@maia.se",
            "emailVerified": True,
            "enabled": True,
            "firstName": "Admin",
            "lastName": "Maia",
            "requiredActions": ["UPDATE_PASSWORD"],
            "credentials": [{"type": "password", "temporary": True, "value": "Admin"}],
        }
    )
    group_id = "user"
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

    groups = keycloak_admin.get_groups()

    users = keycloak_admin.get_users()
    for user in users:
        if "email" in user and user["email"] in ["admin@maia.se"]:
            uid = user["id"]
            for group in groups:
                if group["name"] == "MAIA:" + group_id:
                    gid = group["id"]
                    keycloak_admin.group_user_add(uid, gid)


def change_client_secret(client_secret: str, realm_file: str):
    with open(realm_file, "r") as f:
        realm = json.load(f)
    clients = realm["clients"]
    for idx, client in enumerate(clients):
        if client["clientId"] == "maia":
            clients[idx]["secret"] = client_secret

    with open(realm_file, "w") as f:
        json.dump(realm, f)


def get_arg_parser():
    parser = argparse.ArgumentParser(
        description="Change Keycloak Client Secret",
        epilog=EPILOG,
        formatter_class=RawTextHelpFormatter,
    )
    parser.add_argument("--client_secret", type=str, required=True, help="The client secret to change")
    parser.add_argument("--realm_file", type=str, required=True, help="The realm file to change")
    return parser


def main():
    args = get_arg_parser().parse_args()
    change_client_secret(args.client_secret, args.realm_file)


if __name__ == "__main__":
    main()

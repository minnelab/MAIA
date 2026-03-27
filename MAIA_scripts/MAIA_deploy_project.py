#!/usr/bin/env python

from __future__ import annotations

import requests
import json
import os
import base64
import hashlib
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import yaml
import datetime
from pathlib import Path
from textwrap import dedent
from argparse import ArgumentParser, RawTextHelpFormatter
import MAIA
from loguru import logger

version = MAIA.__version__

TIMESTAMP = "{:%Y-%m-%d_%H-%M-%S}".format(datetime.datetime.now())

DESC = dedent("""
    Script to deploy a MAIA Project through the MAIA Dashboard API.
    """)  # noqa: E501
EPILOG = dedent("""
    Example call:
    ::
        {filename}  --project-config-file /PATH/TO/project_config_file.json
    """.format(filename=Path(__file__).stem))  # noqa: E501


def generate_pkce_pair():
    # 1. Create a secure random string (Verifier)
    verifier_bytes = os.urandom(32)
    code_verifier = base64.urlsafe_b64encode(verifier_bytes).decode("utf-8").rstrip("=")

    # 2. Hash it using SHA-256 and base64 encode it (Challenge)
    challenge_bytes = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode("utf-8").rstrip("=")

    return code_verifier, code_challenge


# --- Step 2 & 3: Local Server to Catch the Redirect ---
class CallbackHandler(BaseHTTPRequestHandler):
    auth_code = None

    def do_GET(self):
        query_components = parse_qs(urlparse(self.path).query)
        if "code" in query_components:
            CallbackHandler.auth_code = query_components["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>Login successful!</h2><p>You can close this window and return to the terminal.</p></body></html>"
            )
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Login failed or no code returned.")


def get_authorization_code(code_challenge, AUTH_URL, CLIENT_ID, REDIRECT_URI, PORT):
    # Construct the login URL
    login_url = (
        f"{AUTH_URL}?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
        f"&scope=openid"
    )

    logger.info("Opening browser for authentication...")
    # If running through ssh and X11 forwarding is not available, print the URL.
    if os.environ.get("SSH_CONNECTION") and not os.environ.get("DISPLAY"):
        logger.info(
            f"\nYou seem to be running through SSH with no local DISPLAY. Please open this URL in your local browser:\n{login_url}\n"
        )
    else:
        webbrowser.open_new(login_url)

    # Start a temporary local server to listen for the Keycloak redirect
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, CallbackHandler)

    # Wait for exactly one request (the redirect from Keycloak)
    httpd.handle_request()

    return CallbackHandler.auth_code


def get_token_with_password(username, password, ca_cert, token_url, client_id, extra_data=None):
    """
    Obtain an OIDC token using username and password authentication (Resource Owner Password Credentials grant).
    """
    data = {
        "grant_type": "password",
        "client_id": "maia",
        "client_secret": os.environ.get("CLIENT_SECRET"),
        "username": username,
        "password": password,
        "scope": "openid",
    }
    if extra_data:
        data.update(extra_data)
    response = requests.post(token_url, data=data, verify=ca_cert)
    response.raise_for_status()
    return response.json().get("access_token")


# --- Step 4: Exchange Code for Token ---
def fetch_token(auth_code, code_verifier, ca_cert, TOKEN_URL, CLIENT_ID, REDIRECT_URI):
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }

    response = requests.post(TOKEN_URL, data=data, verify=ca_cert)
    response.raise_for_status()  # Raise an exception for bad status codes
    return response.json()


def deploy_project(token, dashboard_url, ca_cert, project_config_file):
    url = f"{dashboard_url}/maia/user-management/project-chart/"
    data = json.load(open(project_config_file))
    headers = {
        "Authorization": f"Bearer {token}",
    }
    response = requests.post(url, json=data, headers=headers, verify=ca_cert)
    logger.info(response.status_code)
    if response.status_code == 200:
        logger.info("Project deployed successfully")
        return response.json()["values"]
    else:
        logger.error("Failed to deploy project")
        logger.error(response.text)
        raise Exception(f"Failed to deploy project: {response.text}")


def get_arg_parser():
    pars = ArgumentParser(description=DESC, epilog=EPILOG, formatter_class=RawTextHelpFormatter)

    pars.add_argument(
        "--project-config-file",
        type=str,
        required=True,
        help="JSON configuration file used to extract the project configuration.",
    )
    pars.add_argument(
        "--dashboard-url",
        type=str,
        required=True,
        help="Dashboard URL to use for authentication and deployment.",
    )

    return pars


def main():
    args = get_arg_parser().parse_args()
    project_config_file = args.project_config_file
    dashboard_url = args.dashboard_url
    ca_cert = False
    well_known_url = f"{dashboard_url}/maia/api/well-known/"
    response = requests.get(well_known_url, verify=ca_cert)
    response.raise_for_status()

    well_known_data = response.json()
    KEYCLOAK_URL = well_known_data["issuer"]
    CLIENT_ID = well_known_data["client_id"]
    REDIRECT_URI = "http://localhost:8080"
    PORT = 8080

    AUTH_URL = f"{KEYCLOAK_URL}/protocol/openid-connect/auth"
    TOKEN_URL = f"{KEYCLOAK_URL}/protocol/openid-connect/token"

    try:
        # 1. Generate secrets
        verifier, challenge = generate_pkce_pair()

        logger.info("\nAuthorization code received! Exchanging for token...")
        # 4. Swap code for tokens
        if os.environ.get("MAIA_USERNAME") and os.environ.get("MAIA_PASSWORD") and os.environ.get("CLIENT_SECRET"):
            logger.info("Using username and password authentication")
            token = get_token_with_password(
                os.environ.get("MAIA_USERNAME"), os.environ.get("MAIA_PASSWORD"), ca_cert, TOKEN_URL, CLIENT_ID
            )
            print(token)
        else:
            code = get_authorization_code(challenge, AUTH_URL, CLIENT_ID, REDIRECT_URI, PORT)
            if code:
                tokens = fetch_token(code, verifier, ca_cert, TOKEN_URL, CLIENT_ID, REDIRECT_URI)
                token = tokens.get("id_token")
            else:
                logger.error("No code received")
                raise Exception("No code received")
        resp = deploy_project(token=token, dashboard_url=dashboard_url, ca_cert=ca_cert, project_config_file=project_config_file)
        if "values" in resp and resp["values"] != "":
            project_id = json.load(open(project_config_file))["group_id"]
            with open(f"{project_id}-values.yaml", "w") as f:
                yaml.dump(resp, f)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise Exception(f"An error occurred: {e}")


if __name__ == "__main__":
    main()

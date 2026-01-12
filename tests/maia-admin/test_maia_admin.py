from __future__ import annotations
import pytest
import os
import kubernetes as k8s
import subprocess
import base64
import json
import datetime
import requests
from loguru import logger
from MAIA.kubernetes_utils import get_minio_shareable_link
from types import SimpleNamespace
import tempfile
import yaml
from MAIA.kubernetes_utils import generate_kubeconfig
from requests.auth import HTTPBasicAuth

# Configure logger to use only INFO level and above, printing to stdout
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO")


@pytest.mark.unit
class TestMAIAAdmin:
    """
    Unit tests for verifying the integration and configuration
    of MAIA infrastructure components including ArgoCD, MinIO, Harbor, and Dashboard.
    Each test ensures that core system services are operational and correctly integrated.
    """

    def get_id_token(self, username: str, password: str, client_secret: str, domain: str) -> str:
        """
        Retrieve an OpenID Connect ID token for the specified user.

        Args:
            username (str): Username for Keycloak authentication.
            password (str): Password for Keycloak authentication.
            client_secret (str): OIDC client secret.
            domain (str): Domain for the IAM server.

        Returns:
            str: The obtained ID token.
        """
        token_url = f"https://iam.{domain}/realms/maia/protocol/openid-connect/token"
        auth_data = {
            "grant_type": "password",
            "client_id": "maia",
            "client_secret": client_secret,
            "username": username,
            "password": password,
            "scope": "openid",
        }
        resp = requests.post(token_url, data=auth_data, verify=False)
        resp.raise_for_status()
        return resp.json()["id_token"]

    def setup_method(self, method):
        """
        Prepare environment and test context before each test case.

        Sets up credentials, loads Kubernetes configuration, prepares token(s),
        and checks for required environment variables.
        """
        # Gather required environment variables
        self.domain = os.environ.get("domain")
        self.rancher_token = os.environ.get("rancher_token")
        self.keycloak_client_secret = os.environ.get("keycloak_client_secret")
        self.keycloak_username = os.environ.get("KEYCLOAK_USERNAME")
        self.keycloak_password = os.environ.get("KEYCLOAK_PASSWORD")
        self.argocd_password = os.environ.get("ARGOCD_PASSWORD")
        self.minio_admin_password = os.environ.get("minio_admin_password")
        self.harbor_admin_password = "Harbor12345"  # fallback or default, should be updated if needed

        if not self.domain:
            raise ValueError("The DOMAIN environment variable must be set before running tests.")

        # Determine which id_token to use (Rancher token or freshly generated Keycloak ID token)
        if self.rancher_token:
            self.id_token = self.rancher_token
        else:
            self.id_token = self.get_id_token(
                self.keycloak_username,
                self.keycloak_password,
                self.keycloak_client_secret,
                self.domain,
            )

        # Setup cluster settings
        self.settings = SimpleNamespace(
            OIDC_ISSUER_URL=f"https://iam.{self.domain}/realms/maia",
            OIDC_RP_CLIENT_ID="maia",
            OIDC_RP_CLIENT_SECRET=self.keycloak_client_secret,
            CLUSTER_NAMES={f"https://{self.domain}:16443": "maia"},
            PRIVATE_CLUSTERS={},
        )
        self.kube_apiserver = f"https://{self.domain}:16443"
        if self.rancher_token:
            self.settings.PRIVATE_CLUSTERS = {f"https://mgmt.{self.domain}/k8s/clusters/local": self.rancher_token}
            self.settings.CLUSTER_NAMES = {f"https://mgmt.{self.domain}/k8s/clusters/local": "maia"}
            self.kube_apiserver = f"https://mgmt.{self.domain}/k8s/clusters/local"

        # Generate and persist kubeconfig for test session
        self.kubeconfig = generate_kubeconfig(self.id_token, "test", "default", "maia", self.settings)
        tmp_kubeconfig = tempfile.NamedTemporaryFile(delete=False, suffix=".yaml")
        with open(tmp_kubeconfig.name, "w") as f:
            yaml.dump(self.kubeconfig, f)
        os.environ["KUBECONFIG"] = tmp_kubeconfig.name

        # Attempt to load kubeconfig
        try:
            k8s.config.load_kube_config(tmp_kubeconfig.name)
        except Exception as exc:
            logger.error(f"Failed to load kube config: {exc}")

        # Disable SSL verification for Kubernetes API (for test setups with self-signed certs)
        configuration = k8s.client.Configuration()
        configuration.verify_ssl = False

    def test_argocd(self):
        """
        Test ArgoCD authentication, project listing, and certificate injection for Harbor registry.
        Verifies ArgoCD can authenticate, list projects, and recognize Harbor's custom CA.
        """
        # Authenticate to ArgoCD and obtain a session token
        login_resp = requests.post(
            f"https://argocd.{self.domain}/api/v1/session",
            json={"username": "admin", "password": self.argocd_password},
            verify=False,
        )
        assert login_resp.status_code == 200
        argo_token = login_resp.json().get("token")
        assert argo_token is not None

        # List projects in ArgoCD and check for expected core projects
        proj_resp = requests.get(
            f"https://argocd.{self.domain}/api/v1/projects",
            headers={"Authorization": f"Bearer {argo_token}"},
            verify=False,
        )
        assert proj_resp.status_code == 200
        projects = [item["metadata"]["name"] for item in proj_resp.json().get("items", [])]
        logger.info(f"Projects: {projects}")
        assert "maia-core" in projects
        assert "maia-admin" in projects

        # Retrieve Harbor ingress CA certificate as required by ArgoCD for image registry trust
        secret_cmd = [
            "kubectl",
            "--kubeconfig",
            os.environ.get("KUBECONFIG"),
            "get",
            "secret",
            "maia-admin-harbor-ingress",
            "--namespace",
            "harbor",
            "-o",
            "json",
        ]
        proc = subprocess.run(secret_cmd, stdout=subprocess.PIPE, check=True)
        secret_data = json.loads(proc.stdout.decode())
        ca_crt_b64 = secret_data["data"].get("ca.crt")
        if not ca_crt_b64:
            raise ValueError("ca.crt not found in secret maia-admin-harbor-ingress")
        ca_cert_bytes = base64.b64decode(ca_crt_b64)

        # Post CA certificate to ArgoCD's certificate management endpoint
        argo_cert_url = f"https://argocd.{self.domain}/api/v1/certificates"
        harbor_registry_host = f"registry.{self.domain}"
        payload = {
            "items": [
                {
                    "serverName": harbor_registry_host,
                    "certType": "https",
                    "certData": base64.b64encode(ca_cert_bytes).decode("utf-8"),
                }
            ]
        }
        headers = {"Authorization": f"Bearer {argo_token}", "Content-Type": "application/json"}
        cert_resp = requests.post(argo_cert_url, json=payload, headers=headers, verify=False)
        assert cert_resp.status_code == 200, f"Failed to add CA cert to ArgoCD: {cert_resp.text}"
        logger.info(f"Successfully added Harbor CA certificate to ArgoCD for {harbor_registry_host}")

        # Validate that ArgoCD recognizes the certificate just injected
        cert_check = subprocess.run(
            [
                "curl",
                "-k",
                f"https://argocd.{self.domain}/api/v1/certificates",
                "-H",
                f"Authorization: Bearer {argo_token}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        certs = json.loads(cert_check.stdout.decode())
        for cert_item in certs["items"]:
            if cert_item["serverName"] == harbor_registry_host:
                assert cert_item["certType"] == "https"
                assert cert_item["serverName"] == harbor_registry_host
                assert cert_item["certInfo"] == "CN=harbor-ca"
                break
        else:
            raise ValueError(f"No certificate found for {harbor_registry_host} in ArgoCD")

    def test_dashboard_minio(self):
        """
        Test MinIO integration from within the Maia dashboard environment.

        - Connects (via exec into dashboard pod) to MinIO using MinIO Python SDK.
        - Checks that required buckets exist, uploads a sample environment file.
        - Requests a shareable signed URL and validates its content via a public API endpoint.
        """
        minio_access_key = "maia-admin"
        minio_secret_key = self.minio_admin_password

        # Find the dashboard pod to exec into
        v1_api = k8s.client.CoreV1Api()
        pods = v1_api.list_namespaced_pod(
            namespace="maia-dashboard",
            label_selector="app.kubernetes.io/name=maia-admin-maia-dashboard",
        )
        if not pods.items:
            # Fallback, match by pod name prefix if label is not set as expected
            pods = v1_api.list_namespaced_pod(namespace="maia-dashboard")
            pod_name = next(
                (pod.metadata.name for pod in pods.items if pod.metadata.name.startswith("maia-admin-maia-dashboard")),
                None,
            )
        else:
            pod_name = pods.items[0].metadata.name

        assert pod_name, "No pod found for deployment maia-admin-maia-dashboard in maia-dashboard namespace"

        kubeconfig_path = os.environ.get("KUBECONFIG")
        # Prepare the inline Python script and Kubernetes exec command
        inline_script = f"""
import os
from minio import Minio
import io

minio_client = Minio(
    'minio:80',
    access_key='{minio_access_key}',
    secret_key='{minio_secret_key}',
    secure=False,
)
# List all buckets
buckets = minio_client.list_buckets()
print('Buckets:', [bucket.name for bucket in buckets])

# Ensure the 'maia-envs' bucket exists
bucket_name = 'maia-envs'
if not minio_client.bucket_exists(bucket_name):
    minio_client.make_bucket(bucket_name)

# Upload a file named test_env with given content
env_content = '''torch
scikit-learn
scipy
numpy
monai
'''

minio_client.put_object(
    bucket_name,
    'test_env',
    io.BytesIO(env_content.encode()),
    length=len(env_content),
    content_type='text/plain'
)
print('Uploaded test_env to maia-envs')

from MAIA.kubernetes_utils import get_minio_shareable_link
from types import SimpleNamespace
settings = SimpleNamespace(
    MINIO_PUBLIC_URL='minio:80',
    MINIO_ACCESS_KEY='{minio_access_key}',
    MINIO_SECRET_KEY='{minio_secret_key}',
    MINIO_PUBLIC_SECURE=False,
    BUCKET_NAME='maia-envs',
)
shareable_link = get_minio_shareable_link('test_env', 'maia-envs', settings)
print('Shareable link:', shareable_link)
"""
        kubectl_cmd = (
            f"kubectl exec --kubeconfig {kubeconfig_path} " f'-n maia-dashboard -it {pod_name} -- python3 -c "{inline_script}"'
        )
        result = subprocess.run(kubectl_cmd, shell=True, capture_output=True, text=True)
        assert result.returncode == 0, f"kubectl exec failed: {result.stderr}"
        logger.info(f"Buckets listed in pod:\n{result.stdout}")

        # Generate and validate MinIO shareable link from outside using public API
        settings = SimpleNamespace(
            MINIO_PUBLIC_URL=f"minio-api.{self.domain}",
            MINIO_ACCESS_KEY=minio_access_key,
            MINIO_SECRET_KEY=minio_secret_key,
            MINIO_PUBLIC_SECURE=True,
            BUCKET_NAME="maia-envs",
        )
        shareable_link = get_minio_shareable_link("test_env", "maia-envs", settings)
        logger.info(f"Shareable link: {shareable_link}")
        assert shareable_link is not None

        response = requests.get(shareable_link, verify=False)
        assert response.status_code == 200
        assert response.text == "torch\nscikit-learn\nscipy\nnumpy\nmonai\n"
        logger.info(f"Response: {response.text}")

    def test_harbor(self):
        """
        Test Harbor registry project and robot management via Harbor API.

        - Creates the 'maia' project if it doesn't exist.
        - Creates a robot account for CI, checks credentials, deletes the robot account.
        """
        project_url = f"https://registry.{self.domain}/api/v2.0/projects"
        project_payload = {"project_name": "maia", "public": False}
        response = requests.post(
            project_url,
            json=project_payload,
            auth=HTTPBasicAuth("admin", self.harbor_admin_password),
            verify=False,  # assumes self-signed cert in test env
        )
        assert response.status_code in (200, 409)
        logger.info(f"Harbor project created (or already exists): {response.json()}")

        robot_payload = {
            "name": "maia-ci",
            "description": "CI robot for MAIA",
            "level": "system",
            "duration": -1,
            "disable": False,
            "permissions": [
                {
                    "kind": "project",
                    "namespace": "maia",
                    "access": [
                        {"resource": "repository", "action": "push", "effect": "allow"},
                        {"resource": "repository", "action": "pull", "effect": "allow"},
                    ],
                }
            ],
        }
        robot_url = f"https://registry.{self.domain}/api/v2.0/robots"
        robot_resp = requests.post(
            robot_url,
            json=robot_payload,
            auth=HTTPBasicAuth("admin", self.harbor_admin_password),
            verify=False,
        )
        assert robot_resp.status_code in (200, 201, 409)
        logger.info(f"Harbor robot created: {robot_resp.json()}")

        robot_name = robot_resp.json().get("name")
        robot_secret = robot_resp.json().get("secret")
        robot_id = robot_resp.json().get("id")
        logger.info(f"Robot credentials: username={robot_name}, password={robot_secret}")

        # Delete the robot account
        requests.delete(
            f"https://registry.{self.domain}/api/v2.0/robots/{robot_id}",
            auth=HTTPBasicAuth("admin", self.harbor_admin_password),
            verify=False,
        )
        logger.info(f"Harbor robot deleted: {robot_resp.json()}")

    def test_maia_dashboard(self):
        """
        Test user and group creation in the MAIA dashboard API endpoints.

        - Creates a new user via dashboard API.
        - Creates a new group associated with that user.
        """
        # Create a test user
        create_user_url = f"https://maia.{self.domain}/maia/user-management/create-user/"
        id_token = self.get_id_token(
            self.keycloak_username,
            self.keycloak_password,
            self.keycloak_client_secret,
            self.domain,
        )
        user_data = {
            "email": f"user@{self.domain}",
            "username": f"user@{self.domain}",
            "first_name": "User",
            "last_name": "User",
            "namespace": "users,test",
        }
        user_headers = {"Authorization": f"Bearer {id_token}"}
        user_resp = requests.post(create_user_url, json=user_data, headers=user_headers, verify=False)

        if user_resp.status_code == 200:
            logger.info(f"User created successfully: {user_resp.json()}")
        else:
            logger.error(f"Failed to create user: {user_resp.text}")
            assert False

        # Create a test group for the user
        create_group_url = "https://maia.maia.io/maia/user-management/create-group/"
        group_data = {
            "group_id": "test",
            "gpu": "NO",
            "date": datetime.date.today().strftime("%Y-%m-%d"),
            "memory_limit": "8Gi",
            "cpu_limit": "4",
            "conda": "test_env",
            "cluster": "maia",
            "minimal_env": "Base",
            "user_id": f"user@{self.domain}",
            "supervisor": f"user@{self.domain}",
            "description": "Test group",
            "email_list": [f"user@{self.domain}"],
        }
        group_headers = {"Authorization": f"Bearer {id_token}"}

        group_resp = requests.post(create_group_url, json=group_data, headers=group_headers, verify=False)
        if group_resp.status_code == 200:
            logger.info(f"Group created successfully: {group_resp.json()}")
        else:
            logger.error(f"Failed to create group: {group_resp.text}")
            assert False

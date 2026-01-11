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
    """ """

    def get_id_token(self, username, password, client_secret, domain):
        """
        Get an ID token for the test user.
        """
        url = f"https://iam.{domain}/realms/maia/protocol/openid-connect/token"
        data = {
            "grant_type": "password",
            "client_id": "maia",
            "client_secret": client_secret,
            "username": username,
            "password": password,
            "scope": "openid",
        }
        r = requests.post(url, data=data, verify=False)
        r.raise_for_status()
        return r.json()["id_token"]

    def setup_method(self, method):
        """
        Setup to be executed at the beginning of each test.
        Loads Kubernetes config and ensures essential environment variables are present.
        """
        # Load K8s config for all tests
        self.rancher_token = os.environ.get("RANCHER_TOKEN")
        self.domain = os.environ.get("DOMAIN")
        self.keycloak_client_secret = os.environ.get("KEYCLOAK_CLIENT_SECRET")
        self.keycloak_username = os.environ.get("KEYCLOAK_USERNAME")
        self.keycloak_password = os.environ.get("KEYCLOAK_PASSWORD")
        self.rancher_token = os.environ.get("RANCHER_TOKEN")
        self.argocd_password = os.environ.get("ARGOCD_PASSWORD")
        self.minio_admin_password = os.environ.get("MINIO_ADMIN_PASSWORD")
        self.harbor_admin_password = "Harbor12345"
        if self.rancher_token is not None:
            self.id_token = self.rancher_token
        else:
            self.id_token = self.get_id_token(
                self.keycloak_username, self.keycloak_password, self.keycloak_client_secret, self.domain
            )

        self.settings = SimpleNamespace(
            OIDC_ISSUER_URL=f"https://iam.{self.domain}/realms/maia",
            OIDC_RP_CLIENT_ID="maia",
            OIDC_RP_CLIENT_SECRET=self.keycloak_client_secret,
            CLUSTER_NAMES={
                f"https://{self.domain}:16443": "maia",
            },
            PRIVATE_CLUSTERS={},
        )
        self.kube_apiserver = f"https://{self.domain}:16443"
        if self.rancher_token is not None:
            self.settings.PRIVATE_CLUSTERS = {
                f"https://mgmt.{self.domain}/k8s/clusters/local": self.rancher_token,
            }
            self.settings.CLUSTER_NAMES = {
                f"https://mgmt.{self.domain}/k8s/clusters/local": "maia",
            }
            self.kube_apiserver = f"https://mgmt.{self.domain}/k8s/clusters/local"
        self.kubeconfig = generate_kubeconfig(self.id_token, "test", "default", "maia", self.settings)

        tmp_kubeconfig = tempfile.NamedTemporaryFile(delete=False, suffix=".yaml")
        with open(tmp_kubeconfig.name, "w") as f:
            yaml.dump(self.kubeconfig, f)

        os.environ["KUBECONFIG"] = tmp_kubeconfig.name

        try:
            k8s.config.load_kube_config(tmp_kubeconfig.name)
        except Exception as e:
            logger.error(f"Failed to load kube config: {e}")

        configuration = k8s.client.Configuration()
        configuration.verify_ssl = False
        # Ensure DOMAIN env var is set (required for most tests)

        if not self.domain:
            raise ValueError("The DOMAIN environment variable must be set before running tests.")

    def test_argocd(self):
        response = requests.post(
            f"https://argocd.{self.domain}/api/v1/session",
            json={"username": "admin", "password": self.argocd_password},
            verify=False,
        )

        assert response.status_code == 200
        assert response.json()["token"] is not None

        token = response.json()["token"]

        response = requests.get(
            f"https://argocd.{self.domain}/api/v1/projects", headers={"Authorization": f"Bearer {token}"}, verify=False
        )
        assert response.status_code == 200
        assert response.json()["items"] is not None
        projects = [item["metadata"]["name"] for item in response.json()["items"]]
        logger.info(f"Projects: {projects}")
        assert "maia-core" in projects
        assert "maia-admin" in projects

        get_secret_cmd = [
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
        result = subprocess.run(get_secret_cmd, stdout=subprocess.PIPE, check=True)
        secret_data = json.loads(result.stdout.decode())

        # Extract the CA certificate
        ca_crt_b64 = secret_data["data"].get("ca.crt")
        if ca_crt_b64 is None:
            raise ValueError("ca.crt not found in secret maia-admin-harbor-ingress")
        ca_crt = base64.b64decode(ca_crt_b64)

        # Add ArgoCD TLS certificate for Harbor registry using ArgoCD API
        # This adds a certificate to ArgoCD settings for the Harbor registry, so ArgoCD can pull images
        argocd_api_url = f"https://argocd.{self.domain}/api/v1/certificates"

        # The CA certificate has already been extracted above into `ca_crt`
        # The hostname used by Harbor for image pulling
        harbor_registry = f"registry.{self.domain}"

        # Construct the payload for the ArgoCD API to add a certificate
        cert_payload = {
            "items": [
                {
                    "serverName": harbor_registry,
                    "certType": "https",
                    "certData": base64.b64encode(ca_crt).decode("utf-8"),
                    # "certInfo": "SHA256:ROQFvPThGrW4RuWLoL9tq9I9zJ42fK4XywyRtbOz/EQ"#ca_crt.decode("utf-8"),
                }
            ]
        }
        # The ArgoCD JWT token obtained earlier
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        resp = requests.post(argocd_api_url, json=cert_payload, headers=headers, verify=False)
        assert resp.status_code == 200, f"Failed to add CA cert to ArgoCD: {resp.text}"
        logger.info(f"Successfully added Harbor CA certificate to ArgoCD for {harbor_registry}")

        result = subprocess.run(
            [
                "curl",
                "-k",
                f"https://argocd.{self.domain}/api/v1/certificates",
                "-H",
                f"Authorization: Bearer {token}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        cert_data = json.loads(result.stdout.decode())
        for cert in cert_data["items"]:
            if cert["serverName"] == harbor_registry:
                assert cert["certType"] == "https"
                assert cert["serverName"] == harbor_registry
                assert cert["certInfo"] == "CN=harbor-ca"
                break
        else:
            raise ValueError(f"No certificate found for {harbor_registry} in ArgoCD")

    def test_dashboard_minio(self):
        minio_access_key = "maia-admin"
        minio_secret_key = self.minio_admin_password

        # Instead of creating a Minio client directly in Python, run the command inside the 'maia-dashboard' pod.
        # Here we use subprocess to execute a shell command in the pod using kubectl exec.
        # This example lists buckets using the 'mc' CLI inside the pod. The pod and namespace names are fixed,
        # and it is assumed that the 'mc' client is present in the pod/container.

        # Construct the kubectl exec command to run 'mc ls minio' inside the 'maia-dashboard' pod
        # Update command if using another s3/minio client inside the pod.
        # Find the first pod in the maia-dashboard namespace that belongs to the 'maia-admin-maia-dashboard' deployment
        v1 = k8s.client.CoreV1Api()
        pods = v1.list_namespaced_pod(
            namespace="maia-dashboard", label_selector="app.kubernetes.io/name=maia-admin-maia-dashboard"
        )
        if not pods.items:
            # Fallback, match by name prefix if labels are not set as expected
            pods = v1.list_namespaced_pod(namespace="maia-dashboard")
            pod_name = next(
                (p.metadata.name for p in pods.items if p.metadata.name.startswith("maia-admin-maia-dashboard")), None
            )
        else:
            pod_name = pods.items[0].metadata.name
        assert pod_name, "No pod found for deployment maia-admin-maia-dashboard in maia-dashboard namespace"
        kubeconfig = os.environ.get("KUBECONFIG")
        kubectl_cmd = f"""kubectl exec --kubeconfig {kubeconfig} -n maia-dashboard -it {pod_name} -- python3 -c "
import os, base64
from minio import Minio
import urllib3

minio_client = Minio(
    'minio:80',
    access_key='{minio_access_key}',
    secret_key='{minio_secret_key}',
    secure=False,
)
# List all buckets
buckets = minio_client.list_buckets()
print('Buckets:', [bucket.name for bucket in buckets])

# Ensure the 'maia_envs' bucket exists
bucket_name = 'maia-envs'
if not minio_client.bucket_exists(bucket_name):
    minio_client.make_bucket(bucket_name)

# Upload a file named test_env with the given content
env_content = '''torch
scikit-learn
scipy
numpy
monai
'''

import io
minio_client.put_object(
    bucket_name,
    'test_env',
    io.BytesIO(env_content.encode()),
    length=len(env_content),
    content_type='text/plain'
)

# Confirm upload
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
" """
        result = subprocess.run(kubectl_cmd, shell=True, capture_output=True, text=True)
        assert result.returncode == 0, f"kubectl exec failed: {result.stderr}"
        logger.info(f"Buckets listed in pod:\n{result.stdout}")

        settings = SimpleNamespace(
            MINIO_PUBLIC_URL=f"minio-api.{self.domain}",
            MINIO_ACCESS_KEY=f"{minio_access_key}",
            MINIO_SECRET_KEY=f"{minio_secret_key}",
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

        url = f"https://registry.{self.domain}/api/v2.0/projects"

        payload = {"project_name": "maia", "public": False}

        r = requests.post(
            url, json=payload, auth=HTTPBasicAuth("admin", self.harbor_admin_password), verify=False  # only if self-signed cert
        )

        assert r.status_code == 200 or r.status_code == 409
        logger.info(f"Harbor project created: {r.json()}")

        payload = {
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

        r = requests.post(
            f"https://registry.{self.domain}/api/v2.0/robots",
            json=payload,
            auth=HTTPBasicAuth("admin", self.harbor_admin_password),
            verify=False,
        )
        assert r.status_code == 200 or r.status_code == 201 or r.status_code == 409
        logger.info(f"Harbor robot created: {r.json()}")
        username = r.json()["name"]
        password = r.json()["secret"]
        id = r.json()["id"]
        logger.info(f"Username: {username}")
        logger.info(f"Password: {password}")

        requests.delete(
            f"https://registry.{self.domain}/api/v2.0/robots/{id}",
            auth=HTTPBasicAuth("admin", self.harbor_admin_password),
            verify=False,
        )
        # assert r.status_code == 200
        logger.info(f"Harbor robot deleted: {r.json()}")

    def test_maia_dashboard(self):
        url = f"https://maia.{self.domain}/maia/user-management/create-user/"
        id_token = self.get_id_token(self.keycloak_username, self.keycloak_password, self.keycloak_client_secret, self.domain)
        ca_cert = False
        data = {
            "email": f"user@{self.domain}",
            "username": f"user@{self.domain}",
            "first_name": "User",
            "last_name": "User",
            "namespace": "users,test",
        }
        headers = {
            "Authorization": f"Bearer {id_token}",
        }
        response = requests.post(url, json=data, headers=headers, verify=ca_cert)

        if response.status_code == 200:
            logger.info(f"User created successfully: {response.json()}")
        else:
            logger.error(f"Failed to create user: {response.text}")
            assert False

        url = "https://maia.maia.io/maia/user-management/create-group/"
        data = {
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

        headers = {
            "Authorization": f"Bearer {id_token}",
        }

        response = requests.post(url, json=data, headers=headers, verify=ca_cert)
        if response.status_code == 200:
            logger.info(f"Group created successfully: {response.json()}")
        else:
            logger.error(f"Failed to create group: {response.text}")
            assert False

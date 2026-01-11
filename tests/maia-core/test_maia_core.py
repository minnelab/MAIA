from __future__ import annotations
import pytest
import os
import kubernetes as k8s
import subprocess
import base64
from minio import Minio
import urllib3
import time
import io
import requests
import json
from loguru import logger
import yaml
from MAIA.kubernetes_utils import generate_kubeconfig
from types import SimpleNamespace

# Configure logger to use only INFO level and above, printing to stdout
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO")

@pytest.mark.unit
class TestMAIACore:
    """
    Collection of tests for validating the core components and services of MAIA.

    These tests verify:
      - Deployment and persistence of an nginx workload.
      - MinIO operator and tenant provisioning and functional object storage.
      - Grafana accessibility, API usage, and dashboard import.
      - Metrics server functionality.
      - Correct GPU node annotations.
      - Presence and correctness of platform certificates.
    """

    def get_id_token(self, username, password, client_secret):
        """
        Get an ID token for the test user.
        """
        url = "https://iam.maia.io/realms/maia/protocol/openid-connect/token"
        data = {
            "grant_type": "password",
            "client_id": "maia",
            "client_secret": client_secret,
            "username": username,
            "password": password,
            "scope": "openid"
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

        if self.rancher_token is not None:
            self.id_token = self.rancher_token
        else:
            self.id_token = self.get_id_token(self.keycloak_username, self.keycloak_password, self.keycloak_client_secret)

        self.settings = SimpleNamespace(
            OIDC_ISSUER_URL=f"https://iam.{self.domain}/realms/maia",
            OIDC_RP_CLIENT_ID="maia",
            OIDC_RP_CLIENT_SECRET=self.keycloak_client_secret,
            CLUSTER_NAMES={
                f"https://{self.domain}:16443": "maia",
            },
            PRIVATE_CLUSTERS={
            }
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
        with open("kubeconfig.yaml", "w") as f:
            yaml.dump(self.kubeconfig, f)

        os.environ["KUBECONFIG"] = "kubeconfig.yaml"

        try:
            k8s.config.load_kube_config()
        except Exception as e:
            logger.error(f"Failed to load kube config: {e}")

        configuration = k8s.client.Configuration()
        configuration.verify_ssl = False
        # Ensure DOMAIN env var is set (required for most tests)
        
        if not self.domain:
            raise ValueError("The DOMAIN environment variable must be set before running tests.")

        # Set some test-wide defaults or reload values if needed in the future
        self.storage_class = "microk8s-hostpath"

    def test_nginx_deployment(self):
        """
        Deploy an nginx application and validate deployment, persistence, and attached storage.

        This test checks:
          - The nginx deployment is correctly created and accessible on the cluster.
          - Configurations for storage class and proper ingress certificate handling.
          - The persistent volume claim for the deployment remains intact after a rollout restart.
        """
        # self.domain and self.storage_class are set in setup_method
        # self.domain = os.environ.get("DOMAIN")
        # self.storage_class = "microk8s-hostpath"

        # k8s.config.load_kube_config() # Already loaded in setup_method

        # Deploy nginx using the appropriate storage class
        nginx_yaml_url = "https://raw.githubusercontent.com/minnelab/MAIA/refs/heads/master/tests/maia-core/nginx.yaml"
        if self.storage_class == "microk8s-hostpath":
            # Replace storageClassName with microk8s-hostpath before applying
            deploy_nginx_cmd = (
                f"curl -s {nginx_yaml_url} | "
                f"DOMAIN={self.domain} envsubst '$DOMAIN' | "
                "sed 's/nfs-client/microk8s-hostpath/g' | "
                "kubectl apply -f -"
            )
        else:
            deploy_nginx_cmd = f"curl -s {nginx_yaml_url} | " f"DOMAIN={self.domain} envsubst '$DOMAIN' | " "kubectl apply -f -"
        subprocess.run(deploy_nginx_cmd, shell=True, check=True)

        # Fetch nginx pod name in the default namespace using label selector
        nginx_pod_name = (
            subprocess.check_output(
                [
                    "kubectl",
                    "--kubeconfig",
                    os.environ["KUBECONFIG"],
                    "get",
                    "pods",
                    "-n",
                    "default",
                    "-l",
                    "app=nginx",
                    "-o",
                    "jsonpath={.items[0].metadata.name}",
                ]
            )
            .decode("utf-8")
            .strip()
        )

        # Prepare dynamic index page content and push to the nginx container
        index_header = f"Testing MAIA on {self.domain}"
        index_body = f"Hello from {self.domain}!"
        update_index_cmd = [
            "kubectl",
            "--kubeconfig",
            os.environ["KUBECONFIG"],
            "exec",
            "-n",
            "default",
            nginx_pod_name,
            "--",
            "sh",
            "-c",
            (
                "curl -fsSL https://raw.githubusercontent.com/minnelab/MAIA/refs/heads/master/tests/maia-core/index.html | "
                f"sed 's/My MAIA Page/{index_header}/g' | "
                f"sed 's/Hello from MAIA!/{index_body}/g' > /usr/share/nginx/html/index.html"
            ),
        ]
        subprocess.run(update_index_cmd, check=True)

        # Retrieve the page from the nginx service over HTTPS using requests
        nginx_url = f"https://test.{self.domain}"
        response = requests.get(nginx_url, verify=False)
        nginx_content = response.text

        # Build the expected content using requests instead of curl
        raw_index_url = "https://raw.githubusercontent.com/minnelab/MAIA/refs/heads/master/tests/maia-core/index.html"
        raw_index_resp = requests.get(raw_index_url)
        raw_index = raw_index_resp.text
        expected_content = raw_index.replace("My MAIA Page", index_header).replace("Hello from MAIA!", index_body)
        assert expected_content == nginx_content

        # Restart nginx deployment to test persistent volume claim (PVC) effectiveness
        subprocess.run(
            [
                "kubectl",
                "--kubeconfig",
                os.environ["KUBECONFIG"],
                "rollout",
                "restart",
                "deployment/nginx",
            ],
            check=True,
        )

        # Retrieve again after restart using requests
        response_after_restart = requests.get(nginx_url, verify=False)
        nginx_content_after_restart = response_after_restart.text
        assert expected_content == nginx_content_after_restart


    def test_minio_tenant(self):
        """
        Validate that the MinIO operator and tenant are deployed correctly and object operations succeed.

        This test ensures:
          - MinIO tenant manifests are rendered and applied with the correct credentials.
          - The resulting MinIO pod becomes ready.
          - Object storage operations (PUT, GET) using Minio Python SDK work as intended.
        """
        # self.domain is set in setup_method
        # self.domain = os.environ.get("DOMAIN")

        # k8s.config.load_kube_config() # Already loaded in setup_method
        # Use base64-encoded credentials to mimic what's expected by MinIO for secrets
        os.environ["MINIO_ACCESS_KEY"] = base64.b64encode("maia-user".encode()).decode()
        os.environ["MINIO_SECRET_KEY"] = base64.b64encode("maia-user-password".encode()).decode()
        os.environ["MINIO_ROOT_USER"] = "root"
        os.environ["MINIO_ROOT_PASSWORD"] = "maiaadmin2026"

        # Apply the minio tenant manifest with relevant variable substitution
        minio_yaml_url = "https://raw.githubusercontent.com/minnelab/MAIA/refs/heads/master/tests/maia-core/minio.yaml"
        apply_minio_cmd = (
            f"curl -s {minio_yaml_url} | "
            f"DOMAIN={self.domain} envsubst '$DOMAIN' | "
            f"MINIO_ACCESS_KEY={os.environ.get('MINIO_ACCESS_KEY')} envsubst '$MINIO_ACCESS_KEY' | "
            f"MINIO_SECRET_KEY={os.environ.get('MINIO_SECRET_KEY')} envsubst '$MINIO_SECRET_KEY' | "
            f"MINIO_ROOT_USER={os.environ.get('MINIO_ROOT_USER')} envsubst '$MINIO_ROOT_USER' | "
            f"MINIO_ROOT_PASSWORD={os.environ.get('MINIO_ROOT_PASSWORD')} envsubst '$MINIO_ROOT_PASSWORD' | "
            "kubectl apply -f -"
        )
        subprocess.run(apply_minio_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Allow time for the MinIO pod to be created and become ready
        time.sleep(10)
        subprocess.run(
            [
                "kubectl",
                "--kubeconfig",
                os.environ["KUBECONFIG"],
                "wait",
                "pod/test-minio-tenant-pool-0-0",
                "-n",
                "default",
                "--for=condition=Ready",
                "--timeout=180s",
            ],
            check=True,
        )

        # Set up Minio client with credentials (decoded from base64)
        minio_client = Minio(
            f"minio-api.test.{self.domain}",
            access_key=base64.b64decode(os.environ.get("MINIO_ACCESS_KEY")).decode(),
            secret_key=base64.b64decode(os.environ.get("MINIO_SECRET_KEY")).decode(),
            secure=True,
            # Disable cert validation for test (self-signed likely)
            http_client=urllib3.PoolManager(cert_reqs="CERT_NONE"),
        )

        # Upload a test text file (object)
        test_file_content = b"Hello, World!"
        minio_client.put_object(
            "mlflow",
            "test.txt",
            io.BytesIO(test_file_content),
            length=len(test_file_content),
            content_type="text/plain",
        )

        # Upload and retrieve a test JSON file
        test_json = {"name": "test.txt", "content": "Hello, World!"}
        minio_client.put_object(
            "mlflow",
            "test.json",
            io.BytesIO(json.dumps(test_json).encode()),
            length=len(json.dumps(test_json)),
            content_type="application/json",
        )
        retrieved_object = minio_client.get_object("mlflow", "test.json")
        retrieved_json = json.loads(retrieved_object.read())
        assert retrieved_json == test_json


    def test_grafana(self):
        """
        Validate Grafana accessibility and API usage.

        This test covers:
          - Admin login and API key management via REST API.
          - Importing a sample dashboard via API.
          - Searching for the imported dashboard, retrieving its content, and creating a snapshot.
        """
        # self.domain is set in setup_method
        # self.domain = os.environ.get("DOMAIN")

        os.environ["GRAFANA_ADMIN_USER"] = "admin"
        os.environ["GRAFANA_ADMIN_PASSWORD"] = "prom-operator"

        # Step 1: Remove any previously generated API keys for a clean state
        grafana_url_root = f"https://grafana.{self.domain}"
        grafana_auth = (os.environ["GRAFANA_ADMIN_USER"], os.environ["GRAFANA_ADMIN_PASSWORD"])
        session = requests.Session()
        session.auth = grafana_auth
        session.verify = False

        key_listing_resp = session.get(f"{grafana_url_root}/api/auth/keys")
        key_listing_resp.raise_for_status()
        api_keys = key_listing_resp.json()
        api_token = None

        for api_key in api_keys:
            if api_key["name"].startswith("cli-generated-token-"):
                delete_url = f"{grafana_url_root}/api/auth/keys/{api_key['id']}"
                del_resp = session.delete(delete_url)
                del_resp.raise_for_status()

        # Step 2: Create a new API key for this test
        if api_token is None:
            timestamp = time.time()
            key_name = f"cli-generated-token-{timestamp}"
            create_payload = {
                "name": key_name,
                "role": "Admin"
            }
            create_key_resp = session.post(
                f"{grafana_url_root}/api/auth/keys",
                headers={"Content-Type": "application/json"},
                data=json.dumps(create_payload)
            )
            create_key_resp.raise_for_status()
            api_token = create_key_resp.json()["key"]

        # Step 3: Import the NVIDIA DCGM Exporter dashboard using the Grafana API
        dashboard_path = "tests/maia-core/NVIDIA-DCGM-Exporter-Dashboard.json"
        with open(dashboard_path, "r") as json_file:
            dashboard_json = json.load(json_file)

        dashboard_json.pop("id", None)
        dashboard_json.pop("uid", None)
        dashboard_import_payload = {
            "dashboard": dashboard_json,
            "folderId": 0,
            "overwrite": True,
        }

        import_resp = requests.post(
            f"{grafana_url_root}/api/dashboards/db",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_token}"
            },
            data=json.dumps(dashboard_import_payload),
            verify=False,
        )
        import_resp.raise_for_status()

        # Step 4: Search for the imported dashboard and generate a snapshot
        search_dashboards_resp = requests.get(
            f"{grafana_url_root}/api/search",
            headers={
                "Authorization": f"Bearer {api_token}"
            },
            verify=False,
        )
        search_dashboards_resp.raise_for_status()
        dashboards = search_dashboards_resp.json()

        dashboard_title = "NVIDIA DCGM Exporter Dashboard"
        for search_result in dashboards:
            if search_result["title"] == dashboard_title:
                dashboard_uid = search_result["uid"]
                dashboard_url = f"{grafana_url_root}/api/dashboards/uid/{dashboard_uid}"
                dashboard_result = requests.get(
                    dashboard_url,
                    headers={"Authorization": f"Bearer {api_token}"},
                    verify=False,
                )
                dashboard_result.raise_for_status()
                dashboard_data = dashboard_result.json()
                # Update dashboard templating variables for snapshot
                templating = dashboard_data["dashboard"]["templating"]["list"]
                for variable in templating:
                    if variable["name"] == "datasource":
                        variable["current"]["text"] = "default"
                        variable["current"]["value"] = "default"
                    elif variable["name"] == "cluster":
                        variable["current"]["text"] = ""
                        variable["current"]["value"] = ""
                    elif variable["name"] == "namespace":
                        variable["current"]["text"] = "maia-dashboard"
                        variable["current"]["value"] = "maia-dashboard"
                # Prepare the snapshot payload
                snapshot_payload = {
                    "dashboard": dashboard_data["dashboard"],
                    "time": {"from": "now-1h", "to": "now"},
                    "timezone": "browser",
                    "name": f"Snapshot of {dashboard_data['dashboard']['title']}",
                    "expires": 3600,
                }
                snapshot_result = requests.post(
                    f"{grafana_url_root}/api/snapshots",
                    headers={
                        "Authorization": f"Bearer {api_token}",
                        "Content-Type": "application/json",
                    },
                    data=json.dumps(snapshot_payload),
                    verify=False,
                )
                snapshot_result.raise_for_status()
                snapshot_json = snapshot_result.json()
                assert snapshot_json["url"].startswith(f"https://grafana.{self.domain}/dashboard/snapshot/")
                logger.info("Grafana Snapshot API response: " + json.dumps(snapshot_json))
    

    def test_metrics_server(self):
        """
        Validate the Kubernetes metrics server is enabled and returning pod-level metrics.

        This test retrieves all metrics for pods and logs relevant metric entries in the 'maia-dashboard' namespace.
        """
        # k8s.config.load_kube_config() # Already loaded in setup_method
        # Instead of using the Kubernetes Python client, get pod metrics from metrics server via direct API request

        token = self.id_token  # Assumed available from setup_method
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        # Disable SSL verification for test environments (otherwise, use proper CA bundles)
        response = requests.get(
            f"{self.kube_apiserver}/apis/metrics.k8s.io/v1beta1/pods",
            headers=headers,
            verify=False,
        )
        response.raise_for_status()
        pod_metrics = response.json()

        pods = []
        for metric in pod_metrics["items"]:
            namespace = metric["metadata"].get("namespace")
            if namespace == "maia-dashboard":
                pod_name = metric["metadata"].get("name")
                containers = metric.get("containers")
                logger.info(f"Pod: {pod_name}: {containers}")
                pods.append(pod_name)
        assert len(pods) > 0
        # Verify pod presence by prefix for key MAIA components in maia-dashboard namespace
        has_dashboard = any(pod.startswith("maia-admin-maia-dashboard") for pod in pods)
        has_mysql = any(pod.startswith("maia-admin-maia-dashboard-mysql") for pod in pods)
        has_minio = any(pod.startswith("admin-minio-tenant") for pod in pods)
        assert has_dashboard, "No pod starting with 'maia-admin-maia-dashboard' found in maia-dashboard namespace"
        assert has_mysql, "No pod starting with 'maia-admin-maia-dashboard-mysql' found in maia-dashboard namespace"
        assert has_minio, "No pod starting with 'admin-minio-tenant' found in maia-dashboard namespace"
    

    def test_gpu_node_annotations(self):
        """
        Verify that GPU node annotations are correctly set.

        For each node, logs the values of standard NVIDIA GPU labels if present. This validates expected provisioning of GPU resources in the cluster.
        """
        # k8s.config.load_kube_config() # Already loaded in setup_method
        # Retrieve node list directly from Kubernetes API via HTTPS request
        
        token = self.id_token
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        # Disable SSL verification for test environments
        response = requests.get(
            f"{self.kube_apiserver}/api/v1/nodes",
            headers=headers,
            verify=False,
        )
        response.raise_for_status()
        nodes = type('Nodes', (), {})()
        import types
        items = []
        for item in response.json()["items"]:
            node = types.SimpleNamespace()
            meta = types.SimpleNamespace()
            meta.name = item["metadata"]["name"]
            meta.labels = item["metadata"].get("labels", {})
            node.metadata = meta
            items.append(node)
        nodes.items = items
        gpu_labels = [
            "nvidia.com/gpu.product",
            "nvidia.com/gpu.count",
            "nvidia.com/gpu.memory",
            "nvidia.com/gpu.replicas",
        ]
        gpu_nodes = []
        for node in nodes.items:
            node_name = node.metadata.name
            for label in gpu_labels:
                if label in node.metadata.labels:
                    logger.info(f"{node_name}: {label} - {node.metadata.labels[label]}")
                    gpu_nodes.append(node_name)
        assert len(gpu_nodes) > 0

    def test_check_certificates(self):
        """
        Check that all expected subdomains in the cluster have valid certificates.

        This test connects to each commonly configured subdomain with openssl, parses certificate alternative names,
        and asserts a DNS SAN is present for the exact subdomain or its wildcard/base domain.
        """
        # self.domain is set in setup_method
        cluster_domain = self.domain

        # List of expected subdomains to validate
        subdomains = [
            "traefik",
            "grafana",
            "dashboard",
            "login",
            "iam",
            "registry",
            "mgmt",
            "minio",
            "argocd",
            "maia",
            "test",
            "minio.test",
            "minio-api.test",
        ]

        for sub in subdomains:
            openssl_cmd = (
                f"openssl s_client -connect {sub}.{cluster_domain}:443 -showcerts </dev/null | "
                'openssl x509 -noout -text | grep -A 1 "DNS"'
            )
            result = subprocess.run(
                openssl_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            cert_output = result.stdout.decode("utf-8")

            # For minio subdomains, fallback check to base "test" due to SAN config
            effective_subdomain = "test" if sub in ["minio.test", "minio-api.test"] else sub
            try:
                assert f"DNS:{effective_subdomain}.{cluster_domain}" in cert_output
                logger.info(f"DNS:{effective_subdomain}.{cluster_domain} found in output")
            except AssertionError:
                assert f"DNS:{cluster_domain}, DNS:*.{cluster_domain}" in cert_output
                logger.info(f"DNS:{cluster_domain}, DNS:*.{cluster_domain} found in output")

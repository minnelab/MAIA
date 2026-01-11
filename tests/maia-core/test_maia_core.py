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

    def test_nginx_deployment(self):
        """
        Deploy an nginx application and validate deployment, persistence, and attached storage.

        This test checks:
          - The nginx deployment is correctly created and accessible on the cluster.
          - Configurations for storage class and proper ingress certificate handling.
          - The persistent volume claim for the deployment remains intact after a rollout restart.
        """
        self.domain = os.environ.get("DOMAIN")
        self.storage_class = "microk8s-hostpath"

        k8s.config.load_kube_config()

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

        # Retrieve the page from the nginx service over HTTPS
        response = subprocess.run(["curl", "-k", f"https://test.{self.domain}"], capture_output=True)
        nginx_content = response.stdout.decode("utf-8")

        # Build the expected content
        raw_index = subprocess.run(
            [
                "curl",
                "-fsSL",
                "https://raw.githubusercontent.com/minnelab/MAIA/refs/heads/master/tests/maia-core/index.html",
            ],
            capture_output=True,
        ).stdout.decode("utf-8")
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

        response_after_restart = subprocess.run(["curl", "-k", f"https://test.{self.domain}"], capture_output=True)
        nginx_content_after_restart = response_after_restart.stdout.decode("utf-8")
        assert expected_content == nginx_content_after_restart

    def test_minio_tenant(self):
        """
        Validate that the MinIO operator and tenant are deployed correctly and object operations succeed.

        This test ensures:
          - MinIO tenant manifests are rendered and applied with the correct credentials.
          - The resulting MinIO pod becomes ready.
          - Object storage operations (PUT, GET) using Minio Python SDK work as intended.
        """
        self.domain = os.environ.get("DOMAIN")

        k8s.config.load_kube_config()
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
        self.domain = os.environ.get("DOMAIN")

        os.environ["GRAFANA_ADMIN_USER"] = "admin"
        os.environ["GRAFANA_ADMIN_PASSWORD"] = "prom-operator"

        # Step 1: Remove any previously generated API keys for a clean state
        list_keys_cmd = [
            "curl",
            "-k",
            "-u",
            f"{os.environ['GRAFANA_ADMIN_USER']}:{os.environ['GRAFANA_ADMIN_PASSWORD']}",
            f"https://grafana.{self.domain}/api/auth/keys",
        ]
        key_listing_result = subprocess.run(list_keys_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        api_keys = json.loads(key_listing_result.stdout.decode("utf-8"))
        api_token = None

        for api_key in api_keys:
            if api_key["name"].startswith("cli-generated-token-"):
                delete_key_cmd = [
                    "curl",
                    "-k",
                    "-X",
                    "DELETE",
                    "-u",
                    f"{os.environ['GRAFANA_ADMIN_USER']}:{os.environ['GRAFANA_ADMIN_PASSWORD']}",
                    f"https://grafana.{self.domain}/api/auth/keys/{api_key['id']}",
                ]
                subprocess.run(delete_key_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        # Step 2: Create a new API key for this test
        if api_token is None:
            timestamp = time.time()
            key_name = f"cli-generated-token-{timestamp}"
            create_key_cmd = [
                "curl",
                "-kX",
                "POST",
                f"https://grafana.{self.domain}/api/auth/keys",
                "-H",
                "Content-Type: application/json",
                "-d",
                f'{{"name":"{key_name}","role":"Admin"}}',
                "-u",
                f"{os.environ['GRAFANA_ADMIN_USER']}:{os.environ['GRAFANA_ADMIN_PASSWORD']}",
            ]
            create_result = subprocess.run(create_key_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            api_token = json.loads(create_result.stdout.decode("utf-8"))["key"]

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

        import_dashboard_cmd = [
            "curl",
            "-k",
            "-X",
            "POST",
            f"https://grafana.{self.domain}/api/dashboards/db",
            "-H",
            "Content-Type: application/json",
            "-H",
            f"Authorization: Bearer {api_token}",
            "-d",
            json.dumps(dashboard_import_payload),
        ]
        subprocess.run(import_dashboard_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        # Step 4: Search for the imported dashboard and generate a snapshot
        search_dashboards_cmd = [
            "curl",
            "-k",
            "-H",
            f"Authorization: Bearer {api_token}",
            f"https://grafana.{self.domain}/api/search",
        ]
        search_result = subprocess.run(search_dashboards_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        dashboards = json.loads(search_result.stdout.decode("utf-8"))

        dashboard_title = "NVIDIA DCGM Exporter Dashboard"
        for search_result in dashboards:
            if search_result["title"] == dashboard_title:
                dashboard_uid = search_result["uid"]
                dashboard_url = f"https://grafana.{self.domain}/api/dashboards/uid/{dashboard_uid}"
                get_dashboard_cmd = [
                    "curl",
                    "-k",
                    "-s",
                    "-H",
                    f"Authorization: Bearer {api_token}",
                    dashboard_url,
                ]
                dashboard_result = subprocess.run(get_dashboard_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                dashboard_data = json.loads(dashboard_result.stdout.decode("utf-8"))
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
                create_snapshot_cmd = [
                    "curl",
                    "-kX",
                    "POST",
                    f"https://grafana.{self.domain}/api/snapshots",
                    "-H",
                    f"Authorization: Bearer {api_token}",
                    "-H",
                    "Content-Type: application/json",
                    "-d",
                    json.dumps(snapshot_payload),
                ]
                snapshot_result = subprocess.run(create_snapshot_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                snapshot_json = json.loads(snapshot_result.stdout.decode("utf-8"))
                assert snapshot_json["url"].startswith(f"https://grafana.{self.domain}/dashboard/snapshot/")
                logger.info("Grafana Snapshot API response: " + snapshot_result.stdout.decode("utf-8"))

    def test_metrics_server(self):
        """
        Validate the Kubernetes metrics server is enabled and returning pod-level metrics.

        This test retrieves all metrics for pods and logs relevant metric entries in the 'maia-dashboard' namespace.
        """
        k8s.config.load_kube_config()
        custom_api = k8s.client.CustomObjectsApi()

        pod_metrics = custom_api.list_cluster_custom_object(group="metrics.k8s.io", version="v1beta1", plural="pods")

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
        k8s.config.load_kube_config()
        v1_api = k8s.client.CoreV1Api()
        nodes = v1_api.list_node(watch=False)
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
        self.domain = os.environ.get("DOMAIN")
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

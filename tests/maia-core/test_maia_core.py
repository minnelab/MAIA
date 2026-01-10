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
import json
from loguru import logger

logger.remove()  # Remove the default handler which prints DEBUG to stdout
logger.add(lambda msg: print(msg, end=""), level="INFO")  # Add a new handler for INFO level and above, printing to stdout

@pytest.mark.unit
class TestMAIACore:
    """Test MAIA Core functions."""

    def test_nginx_deployment(self):
        """Test that the nginx deployment is created. Used to test the correct functionality of cert-manager, nfs-client or microk8s-hostpath storage classes, traefik, and metallb."""

        self.domain = os.environ.get("DOMAIN")
        self.storage_class = "microk8s-hostpath"

        k8s.config.load_kube_config()
        if self.storage_class == "microk8s-hostpath":
            subprocess.run(
                'curl -s https://raw.githubusercontent.com/minnelab/MAIA/refs/heads/master/tests/maia-core/nginx.yaml | '
                f"DOMAIN={self.domain} envsubst '$DOMAIN' | "
                "sed 's/nfs-client/microk8s-hostpath/g' | "
                "kubectl apply -f -",
                shell=True,
                check=True
            )
        else:
            subprocess.run(
                'curl -s https://raw.githubusercontent.com/minnelab/MAIA/refs/heads/master/tests/maia-core/nginx.yaml | '
                f"DOMAIN={self.domain} envsubst '$DOMAIN' | "
                "kubectl apply -f -",
                shell=True,
                check=True
            )
        
        # Get the name of the nginx pod
        nginx_pod_name = subprocess.check_output(
            [
                "kubectl", "--kubeconfig", os.environ["KUBECONFIG"],"get", "pods", "-n", "default", "-l", "app=nginx",
                "-o", "jsonpath={.items[0].metadata.name}"
            ]
        ).decode("utf-8").strip()

        header = f"Testing MAIA on {self.domain}"
        body = f"Hello from {self.domain}!"
        subprocess.run([
            "kubectl", "--kubeconfig", os.environ["KUBECONFIG"], "exec", "-n", "default", nginx_pod_name, "--",
            "sh", "-c",
            f"curl -fsSL https://raw.githubusercontent.com/minnelab/MAIA/refs/heads/master/tests/maia-core/index.html | sed 's/My MAIA Page/{header}/g' | sed 's/Hello from MAIA!/{body}/g' > /usr/share/nginx/html/index.html",
        ], check=True)

        result = subprocess.run(["curl", "-k", "https://test." + self.domain], capture_output=True)
        content = result.stdout.decode("utf-8")
        
        expected_content = subprocess.run(["curl", "-fsSL", "https://raw.githubusercontent.com/minnelab/MAIA/refs/heads/master/tests/maia-core/index.html"], capture_output=True).stdout.decode("utf-8")
        expected_content = expected_content.replace("My MAIA Page", header).replace("Hello from MAIA!", body)
        assert expected_content == content

        # Rollout restart the nginx deployment to verify that the persistent volume claim is working
        subprocess.run(["kubectl", "--kubeconfig", os.environ["KUBECONFIG"], "rollout", "restart", "deployment/nginx"], check=True)
        result = subprocess.run(["curl", "-k", "https://test." + self.domain], capture_output=True)
        content = result.stdout.decode("utf-8")
        assert expected_content == content


    def test_minio_tenant(self):
        """Test that the minio tenant is created. Used to test the correct functionality of minio operator, minio tenant, and minio ingress."""

        self.domain = os.environ.get("DOMAIN")

        k8s.config.load_kube_config()
        os.environ["MINIO_ACCESS_KEY"] = base64.b64encode("maia-user".encode()).decode()
        os.environ["MINIO_SECRET_KEY"] = base64.b64encode("maia-user-password".encode()).decode()
        os.environ["MINIO_ROOT_USER"] = "root"
        os.environ["MINIO_ROOT_PASSWORD"] = "maiaadmin2026"
        result = subprocess.run(
            'curl -s https://raw.githubusercontent.com/minnelab/MAIA/refs/heads/master/tests/maia-core/minio.yaml | '
            f"DOMAIN={self.domain} envsubst '$DOMAIN' | "
            f"MINIO_ACCESS_KEY={os.environ.get('MINIO_ACCESS_KEY')} envsubst '$MINIO_ACCESS_KEY' | "
            f"MINIO_SECRET_KEY={os.environ.get('MINIO_SECRET_KEY')} envsubst '$MINIO_SECRET_KEY' | "
            f"MINIO_ROOT_USER={os.environ.get('MINIO_ROOT_USER')} envsubst '$MINIO_ROOT_USER' | "
            f"MINIO_ROOT_PASSWORD={os.environ.get('MINIO_ROOT_PASSWORD')} envsubst '$MINIO_ROOT_PASSWORD' | "
            "kubectl apply -f -",
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )


        time.sleep(10) # Wait for the minio tenant to be created
        subprocess.run([
            "kubectl", "--kubeconfig", os.environ["KUBECONFIG"],
            "wait", "pod/test-minio-tenant-pool-0-0", "-n", "default",
            "--for=condition=Ready", "--timeout=180s"
        ], check=True)

        minio_client = Minio(
            "minio-api.test." + self.domain,
            access_key=base64.b64decode(os.environ.get("MINIO_ACCESS_KEY")).decode(),
            secret_key=base64.b64decode(os.environ.get("MINIO_SECRET_KEY")).decode(),
            secure=True,
            http_client=urllib3.PoolManager(cert_reqs='CERT_NONE') 
        )
        
        data = b"Hello, World!"  # must be bytes
        minio_client.put_object(
            "mlflow",                # bucket name
            "test.txt",              # object name
            io.BytesIO(data),        # file-like object
            length=len(data),
            content_type="text/plain"         # required
        )

        dict_data = {
            "name": "test.txt",
            "content": "Hello, World!"
        }
        minio_client.put_object("mlflow", "test.json", io.BytesIO(json.dumps(dict_data).encode()), length=len(json.dumps(dict_data)), content_type="application/json")

        response = minio_client.get_object("mlflow", "test.json")
        response_data = response.read()
        assert json.loads(response_data) == dict_data
    
    def test_grafana(self):
        """Test that the grafana is accessible."""

        self.domain = os.environ.get("DOMAIN")
        import subprocess
        os.environ["GRAFANA_ADMIN_USER"] = "admin"
        os.environ["GRAFANA_ADMIN_PASSWORD"] = "prom-operator"


        # Get Existing API Keys
        get_api_keys_command = [
            "curl", "-k",
            "-u", f"{os.environ.get('GRAFANA_ADMIN_USER')}:{os.environ.get('GRAFANA_ADMIN_PASSWORD')}",
            f"https://grafana.{self.domain}/api/auth/keys"
        ]
        get_api_keys_result = subprocess.run(
            get_api_keys_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        api_keys = json.loads(get_api_keys_result.stdout.decode("utf-8"))
        key = None
        for api_key in api_keys:
            if api_key["name"].startswith("cli-generated-token-"):
                delete_api_key_command = [
                    "curl", "-k", "-X", "DELETE",
                    "-u", f"{os.environ.get('GRAFANA_ADMIN_USER')}:{os.environ.get('GRAFANA_ADMIN_PASSWORD')}",
                    f"https://grafana.{self.domain}/api/auth/keys/{api_key['id']}"
                ]
                subprocess.run(
                    delete_api_key_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True
                )

        if key is None:
            timestamp = time.time()
            name = f"cli-generated-token-{timestamp}"
            curl_command = [
                "curl", "-kX", "POST",
                f"https://grafana.{self.domain}/api/auth/keys",
                "-H", "Content-Type: application/json",
                "-d", f'{{"name":"{name}","role":"Admin"}}',
                "-u", f"{os.environ.get('GRAFANA_ADMIN_USER')}:{os.environ.get('GRAFANA_ADMIN_PASSWORD')}"
            ]
            result = subprocess.run(
                curl_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            key = json.loads(result.stdout.decode("utf-8"))["key"]
        
        # Use subprocess to POST the dashboard JSON to Grafana via the API

        with open("tests/maia-core/NVIDIA-DCGM-Exporter-Dashboard.json", "r") as file:
            dashboard_json = json.load(file)

        dashboard_json.pop("id", None)
        dashboard_json.pop("uid", None)

        post_dashboard_payload = {
                "dashboard": dashboard_json,
                "folderId": 0,
                "overwrite": True
            }

        post_dashboard_command = [
            "curl", "-k", "-X", "POST",
            f"https://grafana.{self.domain}/api/dashboards/db",
            "-H", "Content-Type: application/json",
            "-H", f"Authorization: Bearer {key}",
            "-d", json.dumps(post_dashboard_payload)
        ]
        post_result = subprocess.run(
            post_dashboard_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )


        search_command = [
            "curl", "-k",
            "-H", f"Authorization: Bearer {key}",
            f"https://grafana.{self.domain}/api/search"
        ]
        search_result = subprocess.run(
            search_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        search_json = json.loads(search_result.stdout.decode("utf-8"))
        dashboard_title = "NVIDIA DCGM Exporter Dashboard"
        for item in search_json:
            if item["title"] == dashboard_title:
                dashboard_url = f"https://grafana.{self.domain}/api/dashboards/uid/{item['uid']}"
                dashboard_command = [
                    "curl", "-k", "-s",
                    "-H", f"Authorization: Bearer {key}",
                    dashboard_url
                ]
                dashboard_result = subprocess.run(
                    dashboard_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True
                )
                dashboard_json = json.loads(dashboard_result.stdout.decode("utf-8"))
                # Prepare the dashboard payload for snapshot (replace panels content as needed)
                for var in dashboard_json["dashboard"]["templating"]["list"]:
                    if var["name"] == "datasource":
                        var["current"]["text"] = "default"
                        var["current"]["value"] = "default"
                    elif var["name"] == "cluster":
                        var["current"]["text"] = ""
                        var["current"]["value"] = ""
                    elif var["name"] == "namespace":
                        var["current"]["text"] = "maia-dashboard"
                        var["current"]["value"] = "maia-dashboard"

                dashboard_payload = {}
                dashboard_payload["dashboard"] = dashboard_json["dashboard"]
                

                dashboard_payload["time"] = {
                    "from": "now-1h",
                    "to": "now"
                }
                dashboard_payload["timezone"] = "browser"  # or "UTC"

                #dashboard_payload["external"] = True

                dashboard_payload["name"] = f"Snapshot of {dashboard_json['dashboard']['title']}"
                dashboard_payload["expires"] = 3600

                snapshot_command = [
                    "curl", "-kX", "POST",
                    f"https://grafana.{self.domain}/api/snapshots",
                    "-H", f"Authorization: Bearer {key}",
                    "-H", "Content-Type: application/json",
                    "-d", json.dumps(dashboard_payload)
                ]
                snapshot_result = subprocess.run(
                    snapshot_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True
                )
                logger.info("Grafana Snapshot API response: " + snapshot_result.stdout.decode("utf-8"))
    

    def test_metrics_server(self):
        """Test that the metrics server is accessible."""


        k8s.config.load_kube_config()
        api = k8s.client.CustomObjectsApi()

        metrics = api.list_cluster_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            plural="pods"
        )

        for item in metrics["items"]:
            if item["metadata"]["namespace"] == "maia-dashboard":
                logger.info(item["metadata"]["name"] + ": " + str(item["containers"]))

    def test_gpu_node_annotations(self):
        """Test that the gpu node annotations are correct."""

        k8s.config.load_kube_config()
        v1 = k8s.client.CoreV1Api()
        nodes = v1.list_node(watch=False)
        for node in nodes.items:
            if "nvidia.com/gpu.product" in node.metadata.labels:
                logger.info(node.metadata.name + ": " + node.metadata.labels["nvidia.com/gpu.product"])
            if "nvidia.com/gpu.count" in node.metadata.labels:
                logger.info(node.metadata.name + ": " + node.metadata.labels["nvidia.com/gpu.count"])
            if "nvidia.com/gpu.memory" in node.metadata.labels:
                logger.info(node.metadata.name + ": " + node.metadata.labels["nvidia.com/gpu.memory"])
            if "nvidia.com/gpu.replicas" in node.metadata.labels:
                logger.info(node.metadata.name + ": " + node.metadata.labels["nvidia.com/gpu.replicas"])

    def test_check_certificates(self):
        """Check that the certificates are correct."""

        self.domain = os.environ.get("DOMAIN")

        # Replace <cluster_domain> with the actual domain
        cluster_domain = self.domain

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

        for subdomain in subdomains:

            command = f'openssl s_client -connect {subdomain}.{cluster_domain}:443 -showcerts </dev/null | openssl x509 -noout -text | grep -A 1 "DNS"'

            result = subprocess.run(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            output = result.stdout.decode("utf-8")
            
            if subdomain == "minio.test" or subdomain == "minio-api.test":
                subdomain = "test"
            try:
                assert f"DNS:{subdomain}.{cluster_domain}" in output
                logger.info(f"DNS:{subdomain}.{cluster_domain} found in output")
            except AssertionError:
                assert f"DNS:{cluster_domain}, DNS:*.{cluster_domain}" in output
                logger.info(f"DNS:{cluster_domain}, DNS:*.{cluster_domain} found in output")


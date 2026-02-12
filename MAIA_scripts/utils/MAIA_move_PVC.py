#!/usr/bin/env python3

import argparse
import kubernetes
import time
from MAIA.maia_fn import convert_username_to_jupyterhub_username

from loguru import logger

kubernetes.config.load_kube_config()


logger.remove()  # Remove the default handler which prints DEBUG to stdout
logger.add(lambda msg: print(msg, end=""), level="INFO")  # Add a new handler for INFO level and above, printing to stdout


def find_node_with_available_gpu():
    nodes = kubernetes.client.CoreV1Api().list_node().items
    for node in nodes:
        # Find how many pods on this node are requesting a GPU
        core_v1 = kubernetes.client.CoreV1Api()
        pods = core_v1.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node.metadata.name}").items
        gpu_pod_count = 0
        for pod in pods:
            if pod.spec and pod.spec.containers:
                for container in pod.spec.containers:
                    limits = container.resources.limits or {}
                    requests = container.resources.requests or {}
                    # Check if the pod requests a GPU in either limits or requests
                    if "nvidia.com/gpu" in limits or "nvidia.com/gpu" in requests:
                        gpu_pod_count += 1
                        break  # Only count the pod once
        available_gpu_count = int(node.metadata.labels["nvidia.com/gpu.count"]) - gpu_pod_count
        logger.info(
            f"Node {node.metadata.name} has {available_gpu_count}/{int(node.metadata.labels['nvidia.com/gpu.count'])} available GPUs [{node.metadata.labels['nvidia.com/gpu.product']}]"
        )
    return None


def create_job(namespace, pvc_name):
    job = kubernetes.client.V1Job(
        metadata=kubernetes.client.V1ObjectMeta(name=f"pvc-to-nfs-{namespace}-{pvc_name}", namespace=namespace),
        spec=kubernetes.client.V1JobSpec(
            ttl_seconds_after_finished=10,
            template=kubernetes.client.V1PodTemplateSpec(
                spec=kubernetes.client.V1PodSpec(
                    restart_policy="OnFailure",
                    containers=[
                        kubernetes.client.V1Container(
                            name=f"pvc-to-nfs-{namespace}-{pvc_name}",
                            image="alpine",
                            command=["sh", "-c", "cp -r /source/* /destination/"],
                            volume_mounts=[
                                kubernetes.client.V1VolumeMount(name="source", mount_path="/source"),
                                kubernetes.client.V1VolumeMount(name="destination", mount_path="/destination"),
                            ],
                        )
                    ],
                    volumes=[
                        kubernetes.client.V1Volume(
                            name="source",
                            persistent_volume_claim=kubernetes.client.V1PersistentVolumeClaimVolumeSource(claim_name=pvc_name),
                        ),
                        kubernetes.client.V1Volume(
                            name="destination",
                            persistent_volume_claim=kubernetes.client.V1PersistentVolumeClaimVolumeSource(
                                claim_name=f"nfs-{namespace}-{pvc_name}"
                            ),
                        ),
                    ],
                )
            ),
        ),
    )
    kubernetes.client.BatchV1Api().create_namespaced_job(namespace=namespace, body=job)


def wait_for_job(namespace, job_name):
    jobs = kubernetes.client.BatchV1Api().list_namespaced_job(namespace=namespace).items
    for job in jobs:
        if job.metadata.name == job_name:
            logger.info(f"Waiting for job {job.metadata.name} to complete")
            while job.status.succeeded != 1 and job.status.failed != 1:
                time.sleep(1)
                job = kubernetes.client.BatchV1Api().read_namespaced_job(name=job.metadata.name, namespace=namespace)
    return None


def create_nfs_pvc(namespace, pvc_name):
    pvc = kubernetes.client.V1PersistentVolumeClaim(
        metadata=kubernetes.client.V1ObjectMeta(name=f"nfs-{namespace}-{pvc_name}", namespace=namespace),
        spec=kubernetes.client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            storage_class_name="nfs-client",
            resources=kubernetes.client.V1ResourceRequirements(requests={"storage": "10Gi"}),
        ),
    )
    kubernetes.client.CoreV1Api().create_namespaced_persistent_volume_claim(namespace=namespace, body=pvc)


def delete_pvc(namespace, pvc_name):
    kubernetes.client.CoreV1Api().delete_namespaced_persistent_volume_claim(name=pvc_name, namespace=namespace)


def create_job_nfs_to_hostpath(namespace, pvc_name, destination_node):
    job = kubernetes.client.V1Job(
        metadata=kubernetes.client.V1ObjectMeta(name=f"nfs-to-pvc-{namespace}-{pvc_name}", namespace=namespace),
        spec=kubernetes.client.V1JobSpec(
            ttl_seconds_after_finished=10,
            template=kubernetes.client.V1PodTemplateSpec(
                spec=kubernetes.client.V1PodSpec(
                    node_selector={"kubernetes.io/hostname": destination_node},
                    restart_policy="OnFailure",
                    containers=[
                        kubernetes.client.V1Container(
                            name=f"nfs-to-pvc-{namespace}-{pvc_name}",
                            image="alpine",
                            command=["sh", "-c", "cp -r /source/* /destination/"],
                            volume_mounts=[
                                kubernetes.client.V1VolumeMount(name="destination", mount_path="/destination"),
                                kubernetes.client.V1VolumeMount(name="source", mount_path="/source"),
                            ],
                        )
                    ],
                    volumes=[
                        kubernetes.client.V1Volume(
                            name="source",
                            persistent_volume_claim=kubernetes.client.V1PersistentVolumeClaimVolumeSource(
                                claim_name=f"nfs-{namespace}-{pvc_name}"
                            ),
                        ),
                        kubernetes.client.V1Volume(
                            name="destination",
                            persistent_volume_claim=kubernetes.client.V1PersistentVolumeClaimVolumeSource(claim_name=pvc_name),
                        ),
                    ],
                )
            ),
        ),
    )
    kubernetes.client.BatchV1Api().create_namespaced_job(namespace=namespace, body=job)


def create_pvc_from_hostpath(namespace, pvc_name):
    pvc = kubernetes.client.V1PersistentVolumeClaim(
        metadata=kubernetes.client.V1ObjectMeta(name=pvc_name, namespace=namespace),
        spec=kubernetes.client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            storage_class_name="local-path",
            resources=kubernetes.client.V1ResourceRequirements(requests={"storage": "10Gi"}),
        ),
    )
    kubernetes.client.CoreV1Api().create_namespaced_persistent_volume_claim(namespace=namespace, body=pvc)


def get_pods_mounting_pvc(namespace, pvc_name):
    pods = kubernetes.client.CoreV1Api().list_namespaced_pod(namespace=namespace).items
    pod_names = []
    for pod in pods:
        if pod.spec.volumes is not None:
            for volume in pod.spec.volumes:
                if volume.persistent_volume_claim is not None:
                    if volume.persistent_volume_claim.claim_name == pvc_name:
                        pod_names.append(pod.metadata.name)
    return pod_names


def check_if_pvc_exists(namespace, pvc_name):
    try:
        pvc = kubernetes.client.CoreV1Api().read_namespaced_persistent_volume_claim(name=pvc_name, namespace=namespace)
    except kubernetes.client.rest.ApiException as e:
        if e.status == 404:
            return False
        else:
            raise e
    return pvc is not None


def get_arg_parser():
    parser = argparse.ArgumentParser(description="Move a PVC to an NFS server")
    parser.add_argument("--destination-node", type=str, required=True, help="The destination node to move the PVC to")
    parser.add_argument("--namespace", type=str, required=True, help="The namespace of the PVC")
    parser.add_argument("--username", type=str, required=False, help="The username of the PVC")
    parser.add_argument("--pv-name", type=str, required=False, help="The name of the PVC")
    return parser


def main():
    args = get_arg_parser().parse_args()
    if bool(args.username) == bool(args.pv_name):
        raise ValueError("Exactly one of --username or --pv-name must be provided.")

    if args.username:
        jupyterhub_username = convert_username_to_jupyterhub_username(args.username)
        pv_name = f"claim-{jupyterhub_username}"
    elif args.pv_name:
        pv_name = args.pv_name
    else:
        raise ValueError("Exactly one of --username or --pv-name must be provided.")
    # find_node_with_available_gpu()

    pods = get_pods_mounting_pvc(args.namespace, pv_name)
    logger.info(f"Pods mounting PVC {pv_name}: {pods}")
    if len(pods) > 0:
        logger.info(f"Pods found : {pods}, do you want to delete them? (y/n)")
        answer = input()
        if answer == "y":
            for pod in pods:
                kubernetes.client.CoreV1Api().delete_namespaced_pod(name=pod, namespace=args.namespace)
        else:
            logger.info("Manual cleanup required. Exiting...")
            exit(1)
    else:
        logger.info("No pods found mounting the PVC.")

    while len(get_pods_mounting_pvc(args.namespace, pv_name)) > 0:
        logger.info(f"Waiting for pods to be deleted: {get_pods_mounting_pvc(args.namespace, pv_name)}")
        time.sleep(1)

    create_nfs_pvc(args.namespace, pv_name)
    create_job(args.namespace, pv_name)
    time.sleep(5)
    wait_for_job(args.namespace, f"pvc-to-nfs-{args.namespace}-{pv_name}")
    logger.info(f"Job completed for {pv_name}")
    delete_pvc(args.namespace, pv_name)
    logger.info(f"PVC {pv_name} deleted")
    while check_if_pvc_exists(args.namespace, pv_name):
        logger.info(f"Waiting for PVC {pv_name} to be deleted")
        time.sleep(1)
    create_pvc_from_hostpath(args.namespace, pv_name)
    create_job_nfs_to_hostpath(args.namespace, pv_name, args.destination_node)
    time.sleep(5)
    wait_for_job(args.namespace, f"nfs-to-pvc-{args.namespace}-{pv_name}")
    logger.info(f"Job completed for {pv_name}")
    delete_pvc(args.namespace, f"nfs-{args.namespace}-{pv_name}")
    logger.info(f"NFS PVC {pv_name} deleted")


if __name__ == "__main__":
    main()

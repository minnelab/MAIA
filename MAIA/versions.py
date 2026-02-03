import os


def define_maia_core_versions():

    if os.environ.get("PROMETHEUS_CHART_VERSION") is not None:
        prometheus_chart_version = os.environ.get("PROMETHEUS_CHART_VERSION")
    else:
        prometheus_chart_version = "45.5.0"

    if os.environ.get("LOKI_CHART_VERSION") is not None:
        loki_chart_version = os.environ.get("LOKI_CHART_VERSION")
    else:
        loki_chart_version = "2.9.9"

    if os.environ.get("TEMPO_CHART_VERSION") is not None:
        tempo_chart_version = os.environ.get("TEMPO_CHART_VERSION")
    else:
        tempo_chart_version = "1.0.0"

    if os.environ.get("TRAEFIK_CHART_VERSION") is not None:
        traefik_chart_version = os.environ.get("TRAEFIK_CHART_VERSION")
    else:
        traefik_chart_version = "33.2.1"

    if os.environ.get("METALLB_CHART_VERSION") is not None:
        metallb_chart_version = os.environ.get("METALLB_CHART_VERSION")
    else:
        metallb_chart_version = "0.14.9"

    if os.environ.get("CERT_MANAGER_CHART_VERSION") is not None:
        cert_manager_chart_version = os.environ.get("CERT_MANAGER_CHART_VERSION")
    else:
        cert_manager_chart_version = "1.16.2"

    if os.environ.get("GPU_OPERATOR_CHART_VERSION") is not None:
        gpu_operator_chart_version = os.environ.get("GPU_OPERATOR_CHART_VERSION")
    else:
        gpu_operator_chart_version = "25.3.1"

    if os.environ.get("INGRESS_NGINX_CHART_VERSION") is not None:
        ingress_nginx_chart_version = os.environ.get("INGRESS_NGINX_CHART_VERSION")
    else:
        ingress_nginx_chart_version = "4.11.3"

    if os.environ.get("NFS_SERVER_PROVISIONER_CHART_VERSION") is not None:
        nfs_server_provisioner_chart_version = os.environ.get("NFS_SERVER_PROVISIONER_CHART_VERSION")
    else:
        nfs_server_provisioner_chart_version = "4.0.18"

    if os.environ.get("METRICS_SERVER_CHART_VERSION") is not None:
        metrics_server_chart_version = os.environ.get("METRICS_SERVER_CHART_VERSION")
    else:
        metrics_server_chart_version = "3.13.0"

    if os.environ.get("GPU_BOOKING_CHART_VERSION") is not None:
        gpu_booking_chart_version = os.environ.get("GPU_BOOKING_CHART_VERSION")
    else:
        gpu_booking_chart_version = "master"  # "1.0.0"

    if os.environ.get("GPU_BOOKING_CHART_TYPE") is not None:
        gpu_booking_chart_type = os.environ.get("GPU_BOOKING_CHART_TYPE")
    else:
        gpu_booking_chart_type = "git_repo"  # or "helm_repo"

    if os.environ.get("CORE_TOOLKIT_CHART_VERSION") is not None:
        core_toolkit_chart_version = os.environ.get("CORE_TOOLKIT_CHART_VERSION")
    else:
        core_toolkit_chart_version = "master"  # "0.2.3"

    if os.environ.get("CORE_TOOLKIT_CHART_TYPE") is not None:
        core_toolkit_chart_type = os.environ.get("CORE_TOOLKIT_CHART_TYPE")
    else:
        core_toolkit_chart_type = "git_repo"  # or "helm_repo"

    if os.environ.get("CORE_PROJECT_CHART_VERSION") is not None:
        core_project_chart_version = os.environ.get("CORE_PROJECT_CHART_VERSION")
    else:
        core_project_chart_version = "1.1.0"

    if os.environ.get("LOGINAPP_CHART_VERSION") is not None:
        loginapp_chart_version = os.environ.get("LOGINAPP_CHART_VERSION")
    else:
        loginapp_chart_version = "1.3.0"

    if os.environ.get("MINIO_OPERATOR_CHART_VERSION") is not None:
        minio_operator_chart_version = os.environ.get("MINIO_OPERATOR_CHART_VERSION")
    else:
        minio_operator_chart_version = "6.0.4"

    return {
        "prometheus_chart_version": prometheus_chart_version,
        "loki_chart_version": loki_chart_version,
        "tempo_chart_version": tempo_chart_version,
        "traefik_chart_version": traefik_chart_version,
        "metallb_chart_version": metallb_chart_version,
        "cert_manager_chart_version": cert_manager_chart_version,
        "gpu_operator_chart_version": gpu_operator_chart_version,
        "ingress_nginx_chart_version": ingress_nginx_chart_version,
        "nfs_server_provisioner_chart_version": nfs_server_provisioner_chart_version,
        "metrics_server_chart_version": metrics_server_chart_version,
        "gpu_booking_chart_version": gpu_booking_chart_version,
        "gpu_booking_chart_type": gpu_booking_chart_type,
        "core_project_chart_version": core_project_chart_version,
        "core_toolkit_chart_version": core_toolkit_chart_version,
        "core_toolkit_chart_type": core_toolkit_chart_type,
        "loginapp_chart_version": loginapp_chart_version,
        "minio_operator_chart_version": minio_operator_chart_version,
    }


def define_maia_admin_versions():

    if os.environ.get("RANCHER_CHART_VERSION") is not None:
        rancher_chart_version = os.environ.get("RANCHER_CHART_VERSION")
    else:
        rancher_chart_version = "2.13.0"

    if os.environ.get("HARBOR_CHART_VERSION") is not None:
        harbor_chart_version = os.environ.get("HARBOR_CHART_VERSION")
    else:
        harbor_chart_version = "1.18.2"

    if os.environ.get("KEYCLOAK_CHART_VERSION") is not None:
        keycloak_chart_version = os.environ.get("KEYCLOAK_CHART_VERSION")
    else:
        keycloak_chart_version = "24.2.0"

    if os.environ.get("ADMIN_TOOLKIT_CHART_VERSION") is not None:
        admin_toolkit_chart_version = os.environ.get("ADMIN_TOOLKIT_CHART_VERSION")
    else:
        admin_toolkit_chart_version = "master"  # "1.3.5"

    if os.environ.get("ADMIN_TOOLKIT_CHART_TYPE") is not None:
        admin_toolkit_chart_type = os.environ.get("ADMIN_TOOLKIT_CHART_TYPE")
    else:
        admin_toolkit_chart_type = "git_repo"  # or "helm_repo"

    if os.environ.get("MAIA_DASHBOARD_CHART_VERSION") is not None:
        maia_dashboard_chart_version = os.environ.get("MAIA_DASHBOARD_CHART_VERSION")
    else:
        maia_dashboard_chart_version = "master"  # "0.2.2"

    if os.environ.get("MAIA_DASHBOARD_IMAGE_VERSION") is not None:
        maia_dashboard_image_version = os.environ.get("MAIA_DASHBOARD_IMAGE_VERSION")
    else:
        maia_dashboard_image_version = define_docker_image_versions()["maia-dashboard"]

    if os.environ.get("MAIA_DASHBOARD_DEV_TAG_SUFFIX") is not None:
        maia_dashboard_dev_tag_suffix = os.environ.get("MAIA_DASHBOARD_DEV_TAG_SUFFIX")
    else:
        maia_dashboard_dev_tag_suffix = "-dev.1"

    if os.environ.get("MAIA_DASHBOARD_CHART_TYPE") is not None:
        maia_dashboard_chart_type = os.environ.get("MAIA_DASHBOARD_CHART_TYPE")
    else:
        maia_dashboard_chart_type = "git_repo"  # or "helm_repo"

    if os.environ.get("ADMIN_PROJECT_CHART_VERSION") is not None:
        admin_project_chart_version = os.environ.get("ADMIN_PROJECT_CHART_VERSION")
    else:
        admin_project_chart_version = "1.0.0"

    return {
        "rancher_chart_version": rancher_chart_version,
        "harbor_chart_version": harbor_chart_version,
        "keycloak_chart_version": keycloak_chart_version,
        "admin_toolkit_chart_version": admin_toolkit_chart_version,
        "admin_toolkit_chart_type": admin_toolkit_chart_type,
        "maia_dashboard_chart_version": maia_dashboard_chart_version,
        "maia_dashboard_image_version": maia_dashboard_image_version,
        "maia_dashboard_dev_tag_suffix": maia_dashboard_dev_tag_suffix,
        "maia_dashboard_chart_type": maia_dashboard_chart_type,
        "admin_project_chart_version": admin_project_chart_version,
    }


def define_maia_project_versions():

    if os.environ.get("MAIA_NAMESPACE_CHART_VERSION") is not None:
        maia_namespace_chart_version = os.environ.get("MAIA_NAMESPACE_CHART_VERSION")
    else:
        maia_namespace_chart_version = "master"  # "1.7.3"

    if os.environ.get("MAIA_FILEBROWSER_CHART_VERSION") is not None:
        maia_filebrowser_chart_version = os.environ.get("MAIA_FILEBROWSER_CHART_VERSION")
    else:
        maia_filebrowser_chart_version = "master"  # "1.0.0"

    if os.environ.get("MAIA_FILEBROWSER_CHART_TYPE") is not None:
        maia_filebrowser_chart_type = os.environ.get("MAIA_FILEBROWSER_CHART_TYPE")
    else:
        maia_filebrowser_chart_type = "git_repo"  # or "helm_repo"

    if os.environ.get("MAIA_PROJECT_CHART_VERSION") is not None:
        maia_project_chart_version = os.environ.get("MAIA_PROJECT_CHART_VERSION")
    else:
        maia_project_chart_version = "1.7.1"

    if os.environ.get("MAIA_NAMESPACE_CHART_TYPE") is not None:
        maia_namespace_chart_type = os.environ.get("MAIA_NAMESPACE_CHART_TYPE")
    else:
        maia_namespace_chart_type = "git_repo"  # or "helm_repo"

    return {
        "maia_namespace_chart_version": maia_namespace_chart_version,
        "maia_filebrowser_chart_version": maia_filebrowser_chart_version,
        "maia_filebrowser_chart_type": maia_filebrowser_chart_type,
        "maia_project_chart_version": maia_project_chart_version,
        "maia_namespace_chart_type": maia_namespace_chart_type,
    }


def define_maia_docker_versions():

    if os.environ.get("KANIKO_CHART_VERSION") is not None:
        kaniko_chart_version = os.environ.get("KANIKO_CHART_VERSION")
    else:
        kaniko_chart_version = "master"  # "1.0.4"

    if os.environ.get("KANIKO_CHART_TYPE") is not None:
        kaniko_chart_type = os.environ.get("KANIKO_CHART_TYPE")
    else:
        kaniko_chart_type = "git_repo"  # or "helm_repo"

    return {
        "kaniko_chart_version": kaniko_chart_version,
        "kaniko_chart_type": kaniko_chart_type,
    }


def define_docker_image_versions():

    if os.environ.get("MAIA_KUBE_IMAGE_VERSION") is not None:
        maia_kube_image_version = os.environ.get("MAIA_KUBE_IMAGE_VERSION")
    else:
        maia_kube_image_version = "1.0"

    if os.environ.get("MAIA_DASHBOARD_IMAGE_VERSION") is not None:
        maia_dashboard_image_version = os.environ.get("MAIA_DASHBOARD_IMAGE_VERSION")
    else:
        maia_dashboard_image_version = "2.4.1"

    if os.environ.get("MONAI_TOOLKIT_IMAGE_VERSION") is not None:
        monai_toolkit_image_version = os.environ.get("MONAI_TOOLKIT_IMAGE_VERSION")
    else:
        monai_toolkit_image_version = "3.0"

    if os.environ.get("MAIA_XNAT_IMAGE_VERSION") is not None:
        maia_xnat_image_version = os.environ.get("MAIA_XNAT_IMAGE_VERSION")
    else:
        maia_xnat_image_version = "1.0"

    if os.environ.get("MAIA_ORTHANC_IMAGE_VERSION") is not None:
        maia_orthanc_image_version = os.environ.get("MAIA_ORTHANC_IMAGE_VERSION")
    else:
        maia_orthanc_image_version = "1.3"

    if os.environ.get("MAIA_MLFLOW_IMAGE_VERSION") is not None:
        maia_mlflow_image_version = os.environ.get("MAIA_MLFLOW_IMAGE_VERSION")
    else:
        maia_mlflow_image_version = "1.0"

    if os.environ.get("MAIA_FILEBROWSER_IMAGE_VERSION") is not None:
        maia_filebrowser_image_version = os.environ.get("MAIA_FILEBROWSER_IMAGE_VERSION")
    else:
        maia_filebrowser_image_version = "1.0"

    if os.environ.get("MAIA_GPU_BOOKING_ADMISSION_CONTROLLER_IMAGE_VERSION") is not None:
        maia_gpu_booking_admission_controller_image_version = os.environ.get(
            "MAIA_GPU_BOOKING_ADMISSION_CONTROLLER_IMAGE_VERSION"
        )
    else:
        maia_gpu_booking_admission_controller_image_version = "1.0"

    if os.environ.get("MAIA_GPU_BOOKING_POD_TERMINATOR_IMAGE_VERSION") is not None:
        maia_gpu_booking_pod_terminator_image_version = os.environ.get("MAIA_GPU_BOOKING_POD_TERMINATOR_IMAGE_VERSION")
    else:
        maia_gpu_booking_pod_terminator_image_version = "1.0"

    if os.environ.get("MAIA_WORKSPACE_BASE_IMAGE_VERSION") is not None:
        maia_workspace_base_image_version = os.environ.get("MAIA_WORKSPACE_BASE_IMAGE_VERSION")
    else:
        maia_workspace_base_image_version = "1.8.1"

    if os.environ.get("MAIA_WORKSPACE_BASE_NOTEBOOK_IMAGE_VERSION") is not None:
        maia_workspace_base_notebook_image_version = os.environ.get("MAIA_WORKSPACE_BASE_NOTEBOOK_IMAGE_VERSION")
    else:
        maia_workspace_base_notebook_image_version = maia_workspace_base_image_version

    if os.environ.get("MAIA_WORKSPACE_BASE_NOTEBOOK_SSH_IMAGE_VERSION") is not None:
        maia_workspace_base_notebook_ssh_image_version = os.environ.get("MAIA_WORKSPACE_BASE_NOTEBOOK_SSH_IMAGE_VERSION")
    else:
        maia_workspace_base_notebook_ssh_image_version = maia_workspace_base_image_version

    if os.environ.get("MAIA_WORKSPACE_IMAGE_VERSION") is not None:
        maia_workspace_image_version = os.environ.get("MAIA_WORKSPACE_IMAGE_VERSION")
    else:
        maia_workspace_image_version = maia_workspace_base_image_version

    if os.environ.get("MAIA_WORKSPACE_NOTEBOOK_IMAGE_VERSION") is not None:
        maia_workspace_notebook_image_version = os.environ.get("MAIA_WORKSPACE_NOTEBOOK_IMAGE_VERSION")
    else:
        maia_workspace_notebook_image_version = maia_workspace_base_image_version

    if os.environ.get("MAIA_WORKSPACE_NOTEBOOK_SSH_IMAGE_VERSION") is not None:
        maia_workspace_notebook_ssh_image_version = os.environ.get("MAIA_WORKSPACE_NOTEBOOK_SSH_IMAGE_VERSION")
    else:
        maia_workspace_notebook_ssh_image_version = maia_workspace_base_image_version

    if os.environ.get("MAIA_WORKSPACE_NOTEBOOK_SSH_ADDONS_IMAGE_VERSION") is not None:
        maia_workspace_notebook_ssh_addons_image_version = os.environ.get("MAIA_WORKSPACE_NOTEBOOK_SSH_ADDONS_IMAGE_VERSION")
    else:
        maia_workspace_notebook_ssh_addons_image_version = maia_workspace_base_image_version

    if os.environ.get("MAIA_WORKSPACE_BASE_NOTEBOOK_SSH_IMAGE_NAME") is not None:
        maia_workspace_base_notebook_ssh_image_name = os.environ.get("MAIA_WORKSPACE_BASE_NOTEBOOK_SSH_IMAGE_NAME")
    else:
        maia_workspace_base_notebook_ssh_image_name = "maia-workspace-base-notebook-ssh"

    if os.environ.get("MAIA_WORKSPACE_NOTEBOOK_SSH_ADDONS_IMAGE_NAME") is not None:
        maia_workspace_notebook_ssh_addons_image_name = os.environ.get("MAIA_WORKSPACE_NOTEBOOK_SSH_ADDONS_IMAGE_NAME")
    else:
        maia_workspace_notebook_ssh_addons_image_name = "maia-workspace-notebook-ssh-addons"

    if os.environ.get("MAIA_LAB_IMAGE_VERSION") is not None:
        maia_lab_image_version = os.environ.get("MAIA_LAB_IMAGE_VERSION")
    else:
        maia_lab_image_version = maia_workspace_base_image_version

    return {
        "maia-kube": maia_kube_image_version,
        "maia-dashboard": maia_dashboard_image_version,
        "monai-toolkit": monai_toolkit_image_version,
        "maia-xnat": maia_xnat_image_version,
        "maia-orthanc": maia_orthanc_image_version,
        "maia-mlflow": maia_mlflow_image_version,
        "maia-filebrowser": maia_filebrowser_image_version,
        "maia-gpu-booking-admission-controller": maia_gpu_booking_admission_controller_image_version,
        "maia-gpu-booking-pod-terminator": maia_gpu_booking_pod_terminator_image_version,
        "maia-workspace-base": maia_workspace_base_image_version,
        "maia-workspace-base-notebook": maia_workspace_base_notebook_image_version,
        "maia-workspace-base-notebook-ssh": maia_workspace_base_notebook_ssh_image_version,
        "maia-workspace-base-notebook-ssh-image-name": maia_workspace_base_notebook_ssh_image_name,
        "maia-workspace": maia_workspace_image_version,
        "maia-workspace-notebook": maia_workspace_notebook_image_version,
        "maia-workspace-notebook-ssh": maia_workspace_notebook_ssh_image_version,
        "maia-workspace-notebook-ssh-addons": maia_workspace_notebook_ssh_addons_image_version,
        "maia-workspace-notebook-ssh-addons-image-name": maia_workspace_notebook_ssh_addons_image_name,
        "maia-lab": maia_lab_image_version,
    }

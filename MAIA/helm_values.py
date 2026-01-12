from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def read_config_dict_and_generate_helm_values_dict(
    config_dict: Dict[str, Any], kubeconfig_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Read Config Dict and generate helm-ready values dict.

    Parameters
    ----------
    config_dict :
        Config Dict
    kubeconfig_dict :
        Kubeconfig Dict

    Returns
    -------
    Helm values dict

    """
    from MAIA.maia_fn import create_config_map_from_data

    value_dict: Dict[str, Any] = {}
    value_dict["image"] = {}
    value_dict["image"]["repository"] = config_dict["docker_image"]

    if "tag" not in config_dict:
        value_dict["image"]["tag"] = "latest"

    else:
        value_dict["image"]["tag"] = config_dict["tag"]

    value_dict["extraVolumeMounts"] = [{"name": "dshm", "mountPath": "/dev/shm"}]

    if "memory_request" in config_dict:
        value_dict["resources"] = {}  # type: ignore
        value_dict["resources"]["requests"] = {}  # type: ignore
        value_dict["resources"]["limits"] = {}  # type: ignore
        value_dict["resources"]["requests"]["memory"] = config_dict["memory_request"]
        value_dict["resources"]["limits"]["memory"] = config_dict["memory_request"]

    if "cpu_request" in config_dict:
        if "resources" not in value_dict:
            value_dict["resources"] = {}  # type: ignore
            value_dict["resources"]["requests"] = {}  # type: ignore
            value_dict["resources"]["limits"] = {}  # type: ignore

        value_dict["resources"]["requests"]["cpu"] = config_dict["cpu_request"]
        value_dict["resources"]["limits"]["cpu"] = config_dict["cpu_request"]

    if "allocationTime" in config_dict:
        time_multiplier = 24 * 60 * 60  # Days
        if config_dict["allocationTime"][-1] == "s":
            time_multiplier = 1
            config_dict["allocationTime"] = config_dict["allocationTime"][:-1]
        elif config_dict["allocationTime"][-1] == "m":
            time_multiplier = 60
            config_dict["allocationTime"] = config_dict["allocationTime"][:-1]
        elif config_dict["allocationTime"][-1] == "h":
            time_multiplier = 24 * 60
            config_dict["allocationTime"] = config_dict["allocationTime"][:-1]
        elif config_dict["allocationTime"][-1] == "d":
            time_multiplier = 24 * 60 * 60
            config_dict["allocationTime"] = config_dict["allocationTime"][:-1]
    else:
        time_multiplier = 1
        config_dict["allocationTime"] = 0

    value_dict["allocatedTime"] = int(config_dict["allocationTime"]) * time_multiplier

    if "gpu_request" in config_dict and int(config_dict["gpu_request"]) > 0:
        if "resources" not in value_dict:
            value_dict["resources"] = {}
            value_dict["resources"]["limits"] = {}
        value_dict["resources"]["limits"]["nvidia.com/gpu"] = config_dict["gpu_request"]
        value_dict["gpus"] = config_dict["gpu_request"]

    if "persistent_volume" in config_dict:
        for idx, persistent_volume in enumerate(config_dict["persistent_volume"]):
            if idx == 0:
                value_dict["persistentVolume"] = [{}]
            else:
                value_dict["persistentVolume"].append({})
            for persistent_volume_key in persistent_volume:
                value_dict["persistentVolume"][-1][persistent_volume_key] = config_dict["persistent_volume"][idx][
                    persistent_volume_key
                ]

    if "existing_persistent_volume" in config_dict:
        for idx, persistent_volume in enumerate(config_dict["existing_persistent_volume"]):
            if idx == 0:
                value_dict["existingPersistentVolume"] = [{}]
            else:
                value_dict["existingPersistentVolume"].append({})
            for persistent_volume_key in persistent_volume:
                value_dict["existingPersistentVolume"][-1][persistent_volume_key] = config_dict["existing_persistent_volume"][
                    idx
                ][persistent_volume_key]

    if "user_secret" in config_dict:
        value_dict["extraEnv"] = [{"name": "n_users", "value": str(len(config_dict["user_secret"]))}]
        value_dict["user_secrets"] = config_dict["user_secret"]
        if len(config_dict["user_secret"]) == 1:
            for user_secret_param in config_dict["user_secret_params"]:
                value_dict["extraEnv"].append(
                    {
                        "name": user_secret_param,
                        "valueFrom": {"secretKeyRef": {"key": user_secret_param, "name": config_dict["user_secret"][0]}},
                    }
                )
            # value_dict["secretCSIVolume"] = [{"name":"{}-vault-secret".format(config_dict['user_secret'][0].split("-")[1])}]
            # value_dict["extraVolumeMounts"].append({
            #    "name": "csi-secret-0",
            #    "mountPath": "/mnt/secrets-store-0"
            #    #"readOnly": "true"
            # })

        else:
            for user_id, user in enumerate(config_dict["user_secret"]):
                for _, user_secret_param in enumerate(config_dict["user_secret_params"]):
                    value_dict["extraEnv"].append(
                        {
                            "name": user_secret_param + "_{}".format(user_id),
                            "valueFrom": {"secretKeyRef": {"key": user_secret_param, "name": user}},
                        }
                    )
                # if idx == 0:
                #    value_dict["secretCSIVolume"] = [{"name": user}]
                # else:
                #    value_dict["secretCSIVolume"].append({"name": "{}-vault-secret".format(user.split("-")[1])})
                # value_dict["extraVolumeMounts"].append({
                #    "name": "csi-secret-{}".format(user_id),
                #    "mountPath": "/mnt/secrets-store-{}".format(user_id),
                #    "readOnly": "true"
                # })

    single_config_file = True
    if "mount_files" in config_dict:
        if single_config_file:
            for idx, mount_file in enumerate(config_dict["mount_files"]):

                if idx == 0:
                    if (
                        len(config_dict["mount_files"][mount_file]) > 2
                        and config_dict["mount_files"][mount_file][2] == "readOnly"
                    ):
                        value_dict["extraVolumeMounts"].append(
                            {
                                "name": mount_file.lower().replace("_", "-"),
                                "mountPath": config_dict["mount_files"][mount_file][1],
                                "readOnly": True,
                            }
                        )
                    else:
                        value_dict["extraVolumeMounts"].append(
                            {
                                "name": mount_file.lower().replace("_", "-"),
                                "mountPath": config_dict["mount_files"][mount_file][1],
                                "readOnly": False,
                            }
                        )

                    value_dict["extraConfigMapVolumes"] = []

                    value_dict["extraConfigMapVolumes"].append(
                        {
                            "name": mount_file.lower().replace("_", "-"),
                            "configMapName": mount_file.lower().replace("_", "-"),
                            "configMapFile": Path(config_dict["mount_files"][mount_file][0]).name,
                            "configMapPath": Path(config_dict["mount_files"][mount_file][0]).name,
                        }
                    )

            files = []
            file_names = []
            mount_file_config = ""
            for idx, mount_file in enumerate(config_dict["mount_files"]):
                if idx == 0:
                    mount_file_config = mount_file
                with open(config_dict["mount_files"][mount_file][0], "r") as f:
                    files.append(f.read())
                    file_names.append(Path(config_dict["mount_files"][mount_file][0]).name)
                    # d = json.load(f)
            create_config_map_from_data(  # json.dumps(d),
                files, mount_file_config.lower().replace("_", "-"), config_dict["namespace"], kubeconfig_dict, file_names
            )

        else:
            for idx, mount_file in enumerate(config_dict["mount_files"]):

                if len(config_dict["mount_files"][mount_file]) > 2 and config_dict["mount_files"][mount_file][2] == "readOnly":
                    value_dict["extraVolumeMounts"].append(
                        {
                            "name": mount_file.lower().replace("_", "-"),
                            "mountPath": config_dict["mount_files"][mount_file][1],
                            "readOnly": True,
                        }
                    )
                else:
                    value_dict["extraVolumeMounts"].append(
                        {
                            "name": mount_file.lower().replace("_", "-"),
                            "mountPath": config_dict["mount_files"][mount_file][1],
                            "readOnly": False,
                        }
                    )

                with open(config_dict["mount_files"][mount_file][0], "r") as f:
                    # d = json.load(f)
                    create_config_map_from_data(  # json.dumps(d),
                        f.read(),
                        mount_file.lower().replace("_", "-"),
                        config_dict["namespace"],
                        kubeconfig_dict,
                        Path(config_dict["mount_files"][mount_file][0]).name,
                    )

                if idx == 0:
                    value_dict["extraConfigMapVolumes"] = []

                value_dict["extraConfigMapVolumes"].append(
                    {
                        "name": mount_file.lower().replace("_", "-"),
                        "configMapName": mount_file.lower().replace("_", "-"),
                        "configMapFile": Path(config_dict["mount_files"][mount_file][0]).name,
                        "configMapPath": Path(config_dict["mount_files"][mount_file][0]).name,
                    }
                )

    if "env_variables" in config_dict:
        if "extraEnv" not in value_dict:
            value_dict["extraEnv"] = []
        for env_variable in config_dict["env_variables"]:
            value_dict["extraEnv"].append({"name": env_variable, "value": config_dict["env_variables"][env_variable]})

    if "ports" in config_dict:
        value_dict["serviceEnabled"] = "True"

        if "service_type" in config_dict:
            value_dict["service"] = {}
            value_dict["service"]["type"] = config_dict["service_type"]

        else:
            value_dict["service"] = {}
            value_dict["service"]["type"] = "ClusterIP"
        for idx, port in enumerate(config_dict["ports"]):
            if idx == 0:
                value_dict["service"]["ports"] = [
                    {"port": config_dict["ports"][port][0], "targetPort": config_dict["ports"][port][0], "name": port}
                ]
                if "service_type" in config_dict and config_dict["service_type"] != "ClusterIP":
                    value_dict["service"]["ports"][-1]["nodePort"] = config_dict["ports"][port][1]
            else:
                value_dict["service"]["ports"].append(
                    {"port": config_dict["ports"][port][0], "targetPort": config_dict["ports"][port][0], "name": port}
                )
                if "service_type" in config_dict and config_dict["service_type"] != "ClusterIP":
                    value_dict["service"]["ports"][-1]["nodePort"] = config_dict["ports"][port][1]

    if "ingress" in config_dict:
        value_dict["ingress"] = config_dict["ingress"]

    if "node_selector" in config_dict:
        value_dict["nodeSelected"] = config_dict["node_selector"]

    if "gpu_selector" in config_dict:
        for gpu_selection in config_dict["gpu_selector"]:
            value_dict["gpuSelected"] = {}
            value_dict["gpuSelected"][gpu_selection] = config_dict["gpu_selector"][gpu_selection]

    if "deployment" in config_dict:
        value_dict["deploy_as_job"] = False
    if "command" in config_dict:
        value_dict["command"] = config_dict["command"]

    if "image_pull_secret" in config_dict:
        value_dict["imagePullSecrets"] = [{"name": config_dict["image_pull_secret"]}]
    return value_dict

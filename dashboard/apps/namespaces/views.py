from django.contrib.auth.decorators import login_required
from django.template import loader
import yaml
from django.template.defaulttags import register
from MAIA.kubernetes_utils import get_namespaces
import os
from pathlib import Path
from apps.models import MAIAProject
from django.http import HttpResponse

# Create your views here.
from MAIA.kubernetes_utils import get_namespace_details
from MAIA.dashboard_utils import get_allocation_date_for_project, get_project, register_cluster_for_project_in_db
import datetime
from django.conf import settings


@register.filter
def encode_pod_name(value):
    return "jupyter-" + value.replace("-", "-2d").replace("@", "-40").replace(".", "-2e")


@register.filter
def to_hyphen(value):
    return value.replace("_", "-")


@register.filter
def to_str(value):
    """converts int to string"""
    return str(value)


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def get_item_in_list(list, key):
    for element in list:
        if element["username"] == key:
            return element


@register.filter
def get_pvc(volumes, volume_name):
    for volume in volumes:
        if volume["name"] == volume_name:
            if "persistentVolumeClaim" in volume:
                return "PVC: " + volume["persistentVolumeClaim"]["claimName"]
            elif "emptyDir" in volume:
                return "emptyDir"
            elif "hostPath" in volume:
                return "hostPath"
    return "N/A"


@register.filter
def subtract(value, arg):
    return value - arg


@register.filter
def get_job_life_info(job):
    try:
        life_time = job["spec"]["activeDeadlineSeconds"]
        start = datetime.datetime.strptime(job["status"]["startTime"], "%Y-%m-%dT%H:%M:%SZ")
        end = datetime.datetime.strptime(job["status"]["startTime"], "%Y-%m-%dT%H:%M:%SZ") + datetime.timedelta(0, life_time)
        return f"From {start} to {end}"
    except Exception:
        return "NA"


@login_required(login_url="/maia/login/")
def namespace_view(request, namespace_id):

    groups = request.user.groups.all()

    namespaces = []
    for group in groups:
        namespaces.append(str(group).split(":")[-1].lower().replace("_", "-"))

    context = {}
    if namespace_id.lower().replace("_", "-") not in namespaces and not request.user.is_superuser:
        html_template = loader.get_template("home/page-403.html")
        return HttpResponse(html_template.render(context, request))
    else:
        id_token = request.session.get("oidc_id_token")

        user_id = request.user.username
        is_admin = False
        if request.user.is_superuser:
            is_admin = True
        maia_workspace_apps, remote_desktop_dict, ssh_ports, monai_models, orthanc_list, deployed_clusters, nvflare_dashboards = (
            get_namespace_details(settings, id_token, namespace_id, user_id, is_admin=is_admin)
        )

        if len(remote_desktop_dict) == 0:
            remote_desktop_dict = None
        if len(monai_models) == 0:
            monai_models = None
        if len(orthanc_list) == 0:
            orthanc_list = None
        if len(nvflare_dashboards) == 0:
            nvflare_dashboards = None

        groups = request.user.groups.all()

        namespaces = []
        if request.user.is_superuser:
            namespaces = get_namespaces(id_token, api_urls=settings.API_URL, private_clusters=settings.PRIVATE_CLUSTERS)

        else:
            for group in groups:
                if str(group) != "MAIA:users":
                    namespaces.append(str(group).split(":")[-1].lower().replace("_", "-"))

        allocation_date = get_allocation_date_for_project(
            maia_project_model=MAIAProject, group_id=namespace_id, is_namespace_style=True
        )
        if "BACKEND" in os.environ and os.environ["BACKEND"] == "compose":
            cluster_config_dict = {"ssh_hostname": "localhost"}
        else:
            _, cluster_id = get_project(namespace_id, settings=settings, maia_project_model=MAIAProject, is_namespace_style=True)

            cluster_config_path = os.environ["CLUSTER_CONFIG_PATH"]

            if cluster_id is not None:
                cluster_config_dict = yaml.safe_load(Path(cluster_config_path).joinpath(cluster_id + ".yaml").read_text())
            else:
                if len(deployed_clusters) > 0:
                    register_cluster_for_project_in_db(MAIAProject, settings, namespace_id, deployed_clusters[0])
                    cluster_config_dict = yaml.safe_load(
                        Path(cluster_config_path).joinpath(deployed_clusters[0] + ".yaml").read_text()
                    )
                else:
                    cluster_config_dict = {"ssh_hostname": "N/A"}

        context = {
            "maia_workspace_ingress": maia_workspace_apps,
            "namespace": namespace_id,
            # "pods":pods, "nodes": nodes,
            "remote_desktop_dict": remote_desktop_dict,
            "allocation_date": allocation_date,
            "orthanc_list": orthanc_list,
            "monai_models": monai_models,
            "nvflare_dashboards": nvflare_dashboards,
            "id_token": id_token,
            "ssh_ports": ssh_ports,
            "ssh_hostname": cluster_config_dict["ssh_hostname"],
            # "service": service,"ingress":ingress
            # "job":jobs,"pvc":pvc
        }
        context["namespaces"] = namespaces

        if "BACKEND" in os.environ:
            backend = os.environ["BACKEND"]
        else:
            backend = "default"
        context["BACKEND"] = backend
        if request.user.is_superuser:
            context["username"] = request.user.username + " [ADMIN]"
            context["user"] = ["admin"]
        else:
            context["username"] = request.user.username
        html_template = loader.get_template("base_namespace.html")
        return HttpResponse(html_template.render(context, request))

from asyncio import sleep
from django.shortcuts import render
from .forms import ResourceRequestForm
from MAIA.kubernetes_utils import get_namespaces, get_available_resources, get_filtered_available_nodes
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.shortcuts import redirect
import os
from django.conf import settings
from MAIA.maia_fn import convert_username_to_jupyterhub_username
import requests
from django.contrib.auth.decorators import login_required


def get_resources_status(request):
    try:
        id_token = request.session.get("oidc_id_token")
        gpu_dict, cpu_dict, ram_dict, gpu_allocations = get_available_resources(
            id_token=id_token,
            api_urls=settings.API_URL,
            cluster_names=settings.CLUSTER_NAMES,
            private_clusters=settings.PRIVATE_CLUSTERS,
        )
        return JsonResponse({"gpu": gpu_dict, "cpu": cpu_dict, "ram": ram_dict, "gpu_allocations": gpu_allocations}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


def get_gpu_status_summary(request):
    try:
        id_token = request.session.get("oidc_id_token")
        gpu_dict, _, _, gpu_allocations = get_available_resources(
            id_token=id_token,
            api_urls=settings.API_URL,
            cluster_names=settings.CLUSTER_NAMES,
            private_clusters=settings.PRIVATE_CLUSTERS,
        )
        gpu_info = {}
        for node in gpu_dict:
            gpu_name = gpu_dict[node][2].split(",")[0]  # Get the GPU name without version
            if gpu_name != "N/A":
                if gpu_name not in gpu_info:
                    gpu_info[gpu_name] = int(gpu_dict[node][0])
                else:
                    gpu_info[gpu_name] += int(gpu_dict[node][0])
        return JsonResponse({"gpu": gpu_info, "gpu_allocations": gpu_allocations}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required(login_url="/maia/login/")
def delete_expired_pod(request, namespace, pod_name):

    if not request.user.is_superuser:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({}, request))

    pod_name = "jupyter-" + convert_username_to_jupyterhub_username(pod_name.split(",")[0])

    POD_TERMINATOR_ADDRESS = os.getenv("POD_TERMINATOR_ADDRESS")

    requests.post(f"{POD_TERMINATOR_ADDRESS}/delete-expired-pod", json={"namespace": namespace, "pod_name": pod_name})
    sleep(5)  # Wait for the pod to be deleted
    return redirect("/maia/resources/")


def search_resources(request):
    if not request.user.is_superuser:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({}, request))
    form = ResourceRequestForm(request.POST)

    try:
        id_token = request.session.get("oidc_id_token")
    except Exception:
        return redirect("/maia/login/")

    groups = request.user.groups.all()
    namespaces = []

    if request.user.is_superuser:
        namespaces = get_namespaces(id_token, api_urls=settings.API_URL, private_clusters=settings.PRIVATE_CLUSTERS)

    else:
        for group in groups:
            if str(group) != "MAIA:users":

                namespaces.append(str(group).split(":")[-1].lower().replace("_", "-"))

    if form.is_valid():
        # form.save()
        id_token = request.session.get("oidc_id_token")
        gpu_request = form.cleaned_data.get("gpu_request")
        cpu_request = form.cleaned_data.get("cpu_request")
        memory_request = form.cleaned_data.get("memory_request")
        gpu_dict, cpu_dict, ram_dict, gpu_allocations = get_available_resources(
            id_token=id_token,
            api_urls=settings.API_URL,
            cluster_names=settings.CLUSTER_NAMES,
            private_clusters=settings.PRIVATE_CLUSTERS,
        )

        available_gpu, available_cpu, available_memory = get_filtered_available_nodes(
            gpu_dict, cpu_dict, ram_dict, cpu_request=cpu_request, gpu_request=gpu_request, memory_request=memory_request
        )
        if "BACKEND" in os.environ:
            backend = os.environ["BACKEND"]
        else:
            backend = "default"
        return render(
            request,
            "resources.html",
            {
                "BACKEND": backend,
                "user": ["admin"],
                "username": request.user.username + " [ADMIN]",
                "namespaces": namespaces,
                "gpu_allocations": gpu_allocations,
                "form": form,
                "available_gpu": available_gpu,
                "available_cpu": available_cpu,
                "available_memory": available_memory,
            },
        )
    form = ResourceRequestForm()
    id_token = request.session.get("oidc_id_token")
    _, _, _, gpu_allocations = get_available_resources(
        id_token=id_token,
        api_urls=settings.API_URL,
        cluster_names=settings.CLUSTER_NAMES,
        private_clusters=settings.PRIVATE_CLUSTERS,
    )

    pod_terminator_address = os.getenv("POD_TERMINATOR_ADDRESS")
    if "BACKEND" in os.environ:
        backend = os.environ["BACKEND"]
    else:
        backend = "default"
    return render(
        request,
        "resources.html",
        {
            "BACKEND": backend,
            "POD_TERMINATOR_ADDRESS": pod_terminator_address,
            "user": ["admin"],
            "username": request.user.username + " [ADMIN]",
            "form": form,
            "namespaces": namespaces,
            "gpu_allocations": gpu_allocations,
        },
    )

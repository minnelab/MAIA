from django import template
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.urls import reverse
from django.conf import settings
from django.shortcuts import redirect
from django.template.defaultfilters import register
from MAIA.kubernetes_utils import get_namespaces, get_cluster_status
from MAIA.keycloak_utils import get_groups_in_keycloak
import urllib3
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests
import json
from loguru import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@register.filter
def global_env(key):
    logger.info(f"INFO: checking {key} in settings and os.environ")
    if hasattr(settings, key):
        logger.info(f"INFO: {key} found in settings")
        return True
    if key in os.environ:
        logger.info(f"INFO: {key} found in os.environ")
        return True

    logger.info(f"INFO: {key} not found in settings or os.environ")
    return False


@register.filter(name="dict_key")
def dict_key(d):
    return d[0]


@register.filter(name="dict_val")
def dict_val(d):
    return d[1]


@register.filter
def index(indexable, i):
    try:
        return indexable[i]
    except Exception:
        return None


@register.filter
def extract_from_form(form, key):
    try:
        return form[key]
    except Exception:
        return None


@register.filter(name="gpu_type_from_node")
def gpu_type_from_node(nodes, node_name):
    return nodes[node_name]["metadata"]["labels"]["nvidia.com/gpu.product"]


@register.filter(name="gpu_vram_from_node")
def gpu_vram_from_node(nodes, node_name):
    return str(int(nodes[node_name]["metadata"]["labels"]["nvidia.com/gpu.memory"]) / 1024) + " Gi"


@register.filter(name="requested_gpu")
def requested_gpu(requests):
    return requests["nvidia.com/gpu"]


@register.filter(name="get_item")
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def to_space(value):
    return value.replace("-", " ")


@register.filter
def maia(value):
    if "Maia" in value:
        return value.replace("Maia", "MAIA")
    elif "Kth" in value:
        return value.replace("Kth", "KTH")
    else:
        return value


@register.filter
def env(key):
    return os.environ.get(key, None)


@login_required(login_url="/maia/login/")
def index_view(request):

    try:
        id_token = request.session.get("oidc_id_token")
        status, cluster_dict = get_cluster_status(
            id_token, api_urls=settings.API_URL, cluster_names=settings.CLUSTER_NAMES, private_clusters=settings.PRIVATE_CLUSTERS
        )
    except Exception:
        return redirect("/maia/login/")

    # Per-cluster and global health stats for the dashboard
    cluster_stats = {}
    for cluster_name, nodes in cluster_dict.items():
        cs = {"total": len(nodes), "ready": 0, "maintenance": 0, "not_ready": 0}
        for node in nodes:
            node_status = status.get(node, [])
            is_ready = len(node_status) > 0 and str(node_status[0]) == "True"
            in_maintenance = len(node_status) > 1 and bool(node_status[1])
            if is_ready and in_maintenance:
                cs["maintenance"] += 1
            elif is_ready:
                cs["ready"] += 1
            else:
                cs["not_ready"] += 1
        cs["health_pct"] = round(100 * cs["ready"] / cs["total"]) if cs["total"] > 0 else 0
        cluster_stats[cluster_name] = cs
    global_stats = {
        "clusters": len(cluster_dict),
        "total": sum(s["total"] for s in cluster_stats.values()),
        "ready": sum(s["ready"] for s in cluster_stats.values()),
        "maintenance": sum(s["maintenance"] for s in cluster_stats.values()),
        "not_ready": sum(s["not_ready"] for s in cluster_stats.values()),
    }

    context = {
        "segment": "index",
        "status": status,
        "id_token": id_token,
        "clusters": cluster_dict,
        "external_links": settings.CLUSTER_LINKS,
        "cluster_stats": cluster_stats,
        "global_stats": global_stats,
    }
    groups = request.user.groups.all()

    namespaces = []
    is_user = False
    if request.user.is_superuser:
        namespaces_global = get_namespaces(id_token, api_urls=settings.API_URL, private_clusters=settings.PRIVATE_CLUSTERS)
        keycloak_groups = get_groups_in_keycloak(settings)
        for group in keycloak_groups:
            group_name = keycloak_groups[group]
            if group_name.lower().replace("_", "-") in namespaces_global:
                namespaces.append(group_name)
    else:
        for group in groups:
            if str(group) != "MAIA:" + settings.USERS_GROUP:

                namespaces.append(str(group).split(":")[-1].lower().replace("_", "-"))
            else:
                is_user = True

    html_template = loader.get_template("home/index.html")
    context["namespaces"] = namespaces
    if not is_user and not request.user.is_superuser:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render(context, request))
    if request.user.is_superuser:
        context["username"] = request.user.username + " [ADMIN]"
        context["user"] = ["admin"]
    else:
        context["username"] = request.user.username

    if "BACKEND" in os.environ:
        backend = os.environ["BACKEND"]
    else:
        backend = "default"
    context["BACKEND"] = backend
    return HttpResponse(html_template.render(context, request))


@login_required(login_url="/maia/login/")
def pages(request):
    context = {}
    # All resource paths end in .html.
    # Pick out the html file name from the url. And load that template.
    try:

        load_template = request.path.split("/")[-1]
        id_token = request.session.get("oidc_id_token")
        status, cluster_dict = get_cluster_status(
            id_token, api_urls=settings.API_URL, cluster_names=settings.CLUSTER_NAMES, private_clusters=settings.PRIVATE_CLUSTERS
        )
        context = {"status": status, "id_token": id_token, "clusters": cluster_dict, "external_links": settings.CLUSTER_LINKS}

        groups = request.user.groups.all()

        namespaces = []
        is_user = False
        if request.user.is_superuser:
            namespaces_global = get_namespaces(id_token, api_urls=settings.API_URL, private_clusters=settings.PRIVATE_CLUSTERS)
            keycloak_groups = get_groups_in_keycloak(settings)
            for group in keycloak_groups:
                group_name = keycloak_groups[group]
                if group_name.lower().replace("_", "-") in namespaces_global:
                    namespaces.append(group_name)

        else:
            for group in groups:
                if str(group) != "MAIA:" + settings.USERS_GROUP:
                    namespaces.append(str(group).split(":")[-1].lower().replace("_", "-"))
                else:
                    is_user = True
        context["namespaces"] = namespaces

        if load_template == "admin":
            return HttpResponseRedirect(reverse("admin:index"))
        context["segment"] = load_template

        if not is_user and "admin" not in namespaces:
            html_template = loader.get_template("home/page-500.html")
            return HttpResponse(html_template.render(context, request))
        if request.user.is_superuser:
            context["username"] = request.user.username + " [ADMIN]"
            context["user"] = ["admin"]
        else:
            context["username"] = request.user.username

        if "BACKEND" in os.environ:
            backend = os.environ["BACKEND"]
        else:
            backend = "default"
        context["BACKEND"] = backend
        html_template = loader.get_template("home/" + load_template)
        return HttpResponse(html_template.render(context, request))

    except template.TemplateDoesNotExist:

        html_template = loader.get_template("home/page-404.html")
        return HttpResponse(html_template.render(context, request))

    except Exception:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render(context, request))


def maia_docs(request):
    context = {}

    html_template = loader.get_template("List.html")
    return HttpResponse(html_template.render(context, request))


def maia_spotlight(request):
    context = {}

    html_template = loader.get_template("spotlight.html")
    return HttpResponse(html_template.render(context, request))


@login_required(login_url="/maia/login/")
def agent_api_view(request):
    if not request.user.is_superuser:
        html_template = loader.get_template("home/page-403.html")
        return HttpResponse(html_template.render({}, request))

    provider = getattr(settings, "AGENT_PROVIDER", os.environ.get("AGENT_PROVIDER", "anthropic")).lower()

    if provider == "openai":
        is_ready = bool(getattr(settings, "OPENAI_API_KEY", None))
        active_model = getattr(settings, "OPENAI_MODEL", "gpt-4o")
        active_base_url = getattr(settings, "OPENAI_BASE_URL", "https://api.openai.com/v1")
    elif provider == "ollama":
        is_ready = True
        active_model = getattr(settings, "OPENWEBAI_MODEL", "llama3")
        active_base_url = getattr(settings, "OPENWEBAI_URL", "http://localhost:11434/v1")
    else:
        provider = "anthropic"
        is_ready = bool(getattr(settings, "ANTHROPIC_API_KEY", None))
        active_model = getattr(settings, "AGENT_MODEL", "claude-sonnet-4-6")
        active_base_url = None

    context = {
        "segment": "agent-api",
        "hostname": getattr(settings, "HOSTNAME", "localhost"),
        "agent_provider": provider,
        "agent_is_ready": is_ready,
        "agent_model": active_model,
        "agent_base_url": active_base_url,
        "agent_token_configured": bool(getattr(settings, "AGENT_API_TOKEN", None)),
        # legacy keys kept for the env-var table
        "anthropic_configured": bool(getattr(settings, "ANTHROPIC_API_KEY", None)),
        "openai_configured": bool(getattr(settings, "OPENAI_API_KEY", None)),
        "ollama_key_configured": bool(getattr(settings, "OPENWEBAI_API_KEY", None)),
        "user": ["admin"],
        "username": request.user.username + " [ADMIN]",
    }
    html_template = loader.get_template("home/agent-api.html")
    return HttpResponse(html_template.render(context, request))


@csrf_exempt
def chat(request):
    if request.method == "POST":
        data = json.loads(request.body)
        user_message = data.get("message", "")
        if not settings.OPENWEBAI_API_KEY or not settings.OPENWEBAI_URL or not settings.OPENWEBAI_MODEL:
            return JsonResponse({"error": "OPENWEBAI_API_KEY or OPENWEBAI_URL or OPENWEBAI_MODEL is not set"}, status=500)
        headers = {
            "Authorization": f"Bearer {settings.OPENWEBAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.OPENWEBAI_MODEL,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message},
            ],
        }
        response = requests.post(
            settings.OPENWEBAI_URL,
            headers=headers,
            json=payload,
        )

        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
            return JsonResponse({"reply": reply})
        return JsonResponse({"error": response.text}, status=500)

    return JsonResponse({"error": "Invalid method"}, status=405)

import os
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.template import loader
from django.conf import settings
from kubernetes import config
from django.contrib.auth.models import User
from pathlib import Path
from .forms import UserTableForm
from apps.models import MAIAUser, MAIAProject
import json
import time
from MAIA.kubernetes_utils import (
    generate_kubeconfig,
    create_helm_repo_secret_from_context,
    create_docker_registry_secret_from_context,
)
from MAIA.dashboard_utils import update_user_table, get_project, get_project_argo_status_and_user_table
from MAIA.kubernetes_utils import create_namespace
from rest_framework.response import Response
from MAIA.keycloak_utils import (
    get_user_ids,
    register_user_in_keycloak,
    register_group_in_keycloak,
    register_users_in_group_in_keycloak,
    get_list_of_groups_requesting_a_user,
    get_list_of_users_requesting_a_group,
    delete_group_in_keycloak,
    get_groups_for_user,
    remove_user_from_group_in_keycloak,
    get_maia_users_from_keycloak,
)
import urllib3
import yaml
from django.shortcuts import redirect
from MAIA_scripts.MAIA_install_project_toolkit import deploy_maia_toolkit_api
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from .services import (
    create_user as create_user_service,
    update_user as update_user_service,
    delete_user as delete_user_service,
    create_group as create_group_service,
    delete_group as delete_group_service,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def verify_id_token(id_token):
    try:
            # Try to validate the id_token using the backend; this will raise an exception if invalid
        backend = OIDCAuthenticationBackend()
        userinfo = backend.verify_token(id_token)
        if not userinfo:
            return Response({"error": "Invalid ID token"}, status=403)
        groups = userinfo.get("groups", [])
        expiration_time = userinfo.get("exp")
        if expiration_time is None:  
            return Response({"error": "Token missing expiration"}, status=403)
        try:  
            expiration_time = int(expiration_time)  
        except (TypeError, ValueError):  
            return Response({"error": "Token has invalid expiration"}, status=403)  
        if expiration_time < time.time():
            return Response({"error": "Token expired"}, status=403)
        if "MAIA:admin" not in groups:
            return Response({"error": "Unauthorized"}, status=403)
    except Exception as e:
        return Response({"error": "Invalid or missing ID token"}, status=403)

    return Response({"message": "Token is valid"}, status=200)


@method_decorator(csrf_exempt, name='dispatch')
class UserManagementAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        id_token = request.query_params.get("token")  
        if not id_token:  
            auth_header = request.headers.get("Authorization")  
            if auth_header:  
                # Support common "Bearer <token>" format  
                if auth_header.lower().startswith("bearer "):  
                    id_token = auth_header[7:]  
                else:  
                    id_token = auth_header 
            # Verify id_token using django-oidc setting

        response = verify_id_token(id_token)
        if response.status_code != 200:
            return Response({"error": response.data["error"]}, status=response.status_code)
        if kwargs.get("path") == "list-users":
            # Return list of users (all MAIAUser emails and ids)
            users = MAIAUser.objects.all().values('id', 'email', 'username', 'namespace')
            keycloak_users = get_maia_users_from_keycloak(settings=settings)
            keycloak_users_by_email = {ku["email"]: ku for ku in keycloak_users}  
            for user in users:  
                keycloak_info = keycloak_users_by_email.get(user["email"])  
                if keycloak_info:  
                    user["keycloak"] = "registered"  
                    user["keycloak_groups"] = keycloak_info.get("groups", [])  
                else:  
                    user["keycloak"] = "not registered"  
                    user["keycloak_groups"] = []  
            return Response({"users": users}, status=200)
        if kwargs.get("path") == "list-groups":
            # Return list of groups (all MAIAProject namespaces)
            groups = MAIAProject.objects.all().values('id', 'namespace', 'gpu', 'date', 'memory_limit', 'cpu_limit', 'conda', 'cluster', 'minimal_env', 'email')
            return Response({"groups": groups}, status=200)

    def post(self, request, *args, **kwargs):
        id_token = request.query_params.get("token")  
        if not id_token:  
            auth_header = request.headers.get("Authorization")  
            if auth_header:  
                # Support common "Bearer <token>" format  
                if auth_header.lower().startswith("bearer "):  
                    id_token = auth_header[7:]  
                else:  
                    id_token = auth_header 
            # Verify id_token using django-oidc setting

        response = verify_id_token(id_token)
        if response.status_code != 200:
            return Response({"error": response.data["error"]}, status=response.status_code)
        if kwargs.get("path") == "create-user":
            required_fields = ["email", "username", "first_name", "last_name", "namespace"]
            missing_fields = [field for field in required_fields if not request.data.get(field)]
            if missing_fields:
                return Response({"error": f"Missing required parameter(s): {', '.join(missing_fields)}"}, status=400)
            # Create a new user
            email = request.data.get("email")
            username = request.data.get("username")
            first_name = request.data.get("first_name")
            last_name = request.data.get("last_name")
            namespace = request.data.get("namespace")
            result = create_user_service(email, username, first_name, last_name, namespace)
            return Response({"message": result["message"]}, status=result["status"])
        elif kwargs.get("path") == "update-user":
            required_fields = ["email", "namespace"]
            missing_fields = [field for field in required_fields if not request.data.get(field)]
            if missing_fields:
                return Response({"error": f"Missing required parameter(s): {', '.join(missing_fields)}"}, status=400)
            # Update a user
            email = request.data.get("email")
            namespace = request.data.get("namespace")
            result = update_user_service(email, namespace)
            return Response({"message": result["message"]}, status=result["status"])
        elif kwargs.get("path") == "delete-user":
            required_fields = ["email"]
            missing_fields = [field for field in required_fields if not request.data.get(field)]
            if missing_fields:
                return Response({"error": f"Missing required parameter(s): {', '.join(missing_fields)}"}, status=400)
            # Delete a user
            email = request.data.get("email")
            result = delete_user_service(email)
            return Response({"message": result["message"]}, status=result["status"])
        elif kwargs.get("path") == "create-group":
            required_fields = ["group_id", "gpu", "date", "memory_limit", "cpu_limit", "conda", "cluster", "minimal_env", "user_id", "user_list"]
            missing_fields = [field for field in required_fields if not request.data.get(field)]
            if missing_fields:
                return Response({"error": f"Missing required parameter(s): {', '.join(missing_fields)}"}, status=400)
            # Create a new group
            group_id = request.data.get("group_id")
            gpu = request.data.get("gpu")
            date = request.data.get("date")
            memory_limit = request.data.get("memory_limit")
            cpu_limit = request.data.get("cpu_limit")
            conda = request.data.get("conda")
            cluster = request.data.get("cluster")
            minimal_env = request.data.get("minimal_env")
            user_id = request.data.get("user_id")
            user_list = request.data.get("user_list", None)
            result = create_group_service(
                group_id, gpu, date, memory_limit, cpu_limit,
                conda, cluster, minimal_env, user_id, user_list
            )
            return Response({"message": result["message"]}, status=result["status"])
        elif kwargs.get("path") == "delete-group":
            required_fields = ["group_id"]
            missing_fields = [field for field in required_fields if not request.data.get(field)]
            if missing_fields:
                return Response({"error": f"Missing required parameter(s): {', '.join(missing_fields)}"}, status=400)
            # Delete a group
            group_id = request.data.get("group_id")
            result = delete_group_service(group_id)
            return Response({"message": result["message"]}, status=result["status"])
        else:
            return Response({"message": "Invalid path"}, status=400)

@method_decorator(csrf_exempt, name="dispatch")  # 🚀 This disables CSRF for this API
class ProjectChartValuesAPIView(APIView):
    permission_classes = [AllowAny]  # 🚀 Allow requests without authentication or CSRF

    def post(self, request, *args, **kwargs):
        try:
            project_form_dict = request.data.get("project_form_dict")
            cluster_id = request.data.get("cluster_id")
            id_token = request.data.get("id_token")
            username = request.data.get("username")

            if not project_form_dict:
                return Response({"error": "Missing Project Form"}, status=400)
            if not cluster_id:
                return Response({"error": "Missing Cluster-ID"}, status=400)
            if not id_token:
                return Response({"error": "Missing ID Token"}, status=400)
            if not username:
                return Response({"error": "Missing Username"}, status=400)

            secret_token = request.data.get("token")
            if not secret_token or secret_token != settings.SECRET_KEY:
                return Response({"error": "Invalid or missing secret token"}, status=403)

            argocd_cluster_id = settings.ARGOCD_CLUSTER

            cluster_config_path = os.environ["CLUSTER_CONFIG_PATH"]
            # maia_config_file = os.environ["MAIA_CONFIG_PATH"]

            kubeconfig_dict = generate_kubeconfig(id_token, username, "default", argocd_cluster_id, settings=settings)
            local_kubeconfig_dict = generate_kubeconfig(id_token, username, "default", cluster_id, settings=settings)
            config.load_kube_config_from_dict(kubeconfig_dict)

            with open(Path("/tmp").joinpath("kubeconfig-project"), "w") as f:
                yaml.dump(kubeconfig_dict, f)
            with open(Path("/tmp").joinpath("kubeconfig-project-local"), "w") as f:
                yaml.dump(local_kubeconfig_dict, f)
                os.environ["KUBECONFIG"] = str(Path("/tmp").joinpath("kubeconfig-project"))
                os.environ["KUBECONFIG_LOCAL"] = str(Path("/tmp").joinpath("kubeconfig-project-local"))

                cluster_config_dict = yaml.safe_load(Path(cluster_config_path).joinpath(cluster_id + ".yaml").read_text())
                # maia_config_dict = yaml.safe_load(Path(maia_config_file).read_text())

                namespace = project_form_dict["group_ID"].lower().replace("_", "-")

                if project_form_dict["environment"] != "Base":
                    registry_url = os.environ.get("MAIA_PRIVATE_REGISTRY", None)
                    if (
                        not Path(cluster_config_path).joinpath(f"MAIA-Cloud_MAIA-KTH-{namespace}.json").exists()
                        and not Path(cluster_config_path).joinpath("MAIA-Cloud-GLOBAL.json").exists()
                    ):
                        html_template = loader.get_template("home/page-500.html")
                        return HttpResponse(
                            html_template.render(
                                {"message": f"The required JSON key does not exist for the project {namespace}"}, request
                            )
                        )

                    if Path(cluster_config_path).joinpath("MAIA-Cloud-GLOBAL.json").exists():
                        credentials_file = Path(cluster_config_path).joinpath("MAIA-Cloud-GLOBAL.json")
                    if Path(cluster_config_path).joinpath(f"MAIA-Cloud_MAIA-KTH-{namespace}.json").exists():
                        credentials_file = Path(cluster_config_path).joinpath(f"MAIA-Cloud_MAIA-KTH-{namespace}.json")
                    try:
                        with open(credentials_file, "r") as f:
                            docker_credentials = json.load(f)
                            r_username = docker_credentials.get("harbor_username")
                            password = docker_credentials.get("harbor_password")
                    except Exception:
                        with open(credentials_file, "r") as f:
                            docker_credentials = f.read()
                            r_username = "_json_key"
                            password = docker_credentials

                    config.load_kube_config_from_dict(local_kubeconfig_dict)

                    create_docker_registry_secret_from_context(
                        docker_credentials={
                            "registry": "https://" + registry_url.split("/")[0],
                            "username": r_username,
                            "password": password,
                        },
                        namespace=namespace,
                        secret_name=registry_url.replace(".", "-").replace("/", "-"),
                    )
                    os.environ["JSON_KEY_PATH"] = str(credentials_file)

                config.load_kube_config_from_dict(kubeconfig_dict)
                os.environ["KUBECONFIG"] = str(Path("/tmp").joinpath("kubeconfig-project"))
                disable_argocd = True
                response = deploy_maia_toolkit_api(
                    project_form_dict=project_form_dict,
                    # maia_config_dict=maia_config_dict,
                    cluster_config_dict=cluster_config_dict,
                    config_folder="/config",  # config_path,
                    redeploy_enabled=True,
                    minimal=(project_form_dict["environment"] == "Base"),
                    no_argocd=disable_argocd,
                    return_values_only=True,
                )
                return Response({"project_values": response}, status=200)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


# Create your views here.
@login_required(login_url="/maia/login/")
def index(request):
    if not request.user.is_superuser:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({}, request))

    argocd_url = settings.ARGOCD_SERVER

    keycloak_users = get_user_ids(settings=settings)

    for keycloak_user in keycloak_users:
        if User.objects.filter(email=keycloak_user).exists():
            ...  # do nothing
        else:
            MAIAUser.objects.create(
                email=keycloak_user, username=keycloak_user, namespace=",".join(keycloak_users[keycloak_user])
            )

    to_register_in_groups, to_register_in_keycloak, maia_groups_dict, project_argo_status, users_to_remove_from_group = (
        get_project_argo_status_and_user_table(
            settings=settings, request=request, maia_user_model=MAIAUser, maia_project_model=MAIAProject
        )
    )

    print("Users to Register in Keycloak: ", to_register_in_keycloak)
    print("Users to Register in Groups: ", to_register_in_groups)
    print("Users to Remove from Group: ", users_to_remove_from_group)

    if request.method == "POST":

        user_list = list(MAIAUser.objects.all().values())

        for user in user_list:
            if user["email"] in to_register_in_keycloak:
                user["is_registered_in_keycloak"] = 0
            else:
                user["is_registered_in_keycloak"] = 1
            if user["email"] in to_register_in_groups:
                user["is_registered_in_groups"] = to_register_in_groups[user["email"]]
            else:
                user["is_registered_in_groups"] = 1
            if user["email"] in users_to_remove_from_group:
                user["remove_from_group"] = users_to_remove_from_group[user["email"]]
            else:
                user["remove_from_group"] = 0

        # Sort users: put at the beginning if user needs action (not registered in keycloak, needs group registration, or needs removal from group)
        sorted_user_list = sorted(
            user_list,
            key=lambda x: not (
                x["is_registered_in_keycloak"] == 0 or x["is_registered_in_groups"] != 1 or x["remove_from_group"] != 0
            ),
        )
        if "BACKEND" in os.environ:
            backend = os.environ["BACKEND"]
        else:
            backend = "default"
        context = {
            "BACKEND": backend,
            "user_table": sorted_user_list,
            "minio_console_url": os.environ.get("MINIO_CONSOLE_URL", None),
            "maia_groups_dict": maia_groups_dict,
            "form": UserTableForm(request.POST),
            "project_argo_status": project_argo_status,
            "argocd_url": argocd_url,
            "user": ["admin"],
            "username": request.user.username + " [ADMIN]",
        }
        html_template = loader.get_template("base_user_management.html")

        form = UserTableForm(request.POST)

        if form.is_valid():
            update_user_table(form, User, MAIAUser, MAIAProject)
        else:
            ...
            # update_user_table(form, User, MAIAUser, MAIAProject)

        return HttpResponse(html_template.render(context, request))

    user_list = list(MAIAUser.objects.all().values())

    for user in user_list:
        if user["email"] in to_register_in_keycloak:
            user["is_registered_in_keycloak"] = 0
        else:
            user["is_registered_in_keycloak"] = 1
        if user["email"] in to_register_in_groups:
            user["is_registered_in_groups"] = to_register_in_groups[user["email"]]
        else:
            user["is_registered_in_groups"] = 1
        if user["email"] in users_to_remove_from_group:
            user["remove_from_group"] = users_to_remove_from_group[user["email"]]
        else:
            user["remove_from_group"] = 0

    # Sort users: put at the beginning if user needs action (not registered in keycloak, needs group registration, or needs removal from group)
    sorted_user_list = sorted(
        user_list,
        key=lambda x: not (
            x["is_registered_in_keycloak"] == 0 or x["is_registered_in_groups"] != 1 or x["remove_from_group"] != 0
        ),
    )

    user_form = UserTableForm(users=sorted_user_list, projects=maia_groups_dict)
    if "BACKEND" in os.environ:
        backend = os.environ["BACKEND"]
    else:
        backend = "default"
    context = {
        "BACKEND": backend,
        "user_table": sorted_user_list,
        "maia_groups_dict": maia_groups_dict,
        "minio_console_url": os.environ.get("MINIO_CONSOLE_URL", None),
        "form": user_form,
        "user": ["admin"],
        "project_argo_status": project_argo_status,
        "argocd_url": argocd_url,
        "username": request.user.username + " [ADMIN]",
    }

    html_template = loader.get_template("base_user_management.html")
    if not request.user.is_superuser:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({}, request))

    return HttpResponse(html_template.render(context, request))


@login_required(login_url="/maia/login/")
def remove_user_from_group_view(request, email):
    if not request.user.is_superuser:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({}, request))

    desired_groups = get_list_of_groups_requesting_a_user(email=email, user_model=MAIAUser)

    keycloak_groups = get_groups_for_user(email=email, settings=settings)

    for keycloak_group in keycloak_groups:
        if keycloak_group not in desired_groups:
            remove_user_from_group_in_keycloak(email=email, group_id=keycloak_group, settings=settings)

    return redirect("/maia/user-management/")


@login_required(login_url="/maia/login/")
def delete_group_view(request, group_id):
    if not request.user.is_superuser:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({}, request))

    delete_group_in_keycloak(group_id=group_id, settings=settings)

    MAIAProject.objects.filter(namespace=group_id).delete()

    return redirect("/maia/user-management/")


@login_required(login_url="/maia/login/")
def register_user_view(request, email):
    if not request.user.is_superuser:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({}, request))

    register_user_in_keycloak(email=email, settings=settings)

    return redirect("/maia/user-management/")


@login_required(login_url="/maia/login/")
def register_user_in_group_view(request, email):
    if not request.user.is_superuser:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({}, request))

    groups = get_list_of_groups_requesting_a_user(email=email, user_model=MAIAUser)

    for group_id in groups:
        register_users_in_group_in_keycloak(group_id=group_id, emails=[email], settings=settings)

    return redirect("/maia/user-management/")


@login_required(login_url="/maia/login/")
def register_group_view(request, group_id):
    if not request.user.is_superuser:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({}, request))

    register_group_in_keycloak(group_id=group_id, settings=settings)
    emails = get_list_of_users_requesting_a_group(maia_user_model=MAIAUser, group_id=group_id)

    register_users_in_group_in_keycloak(group_id=group_id, emails=emails, settings=settings)

    return redirect("/maia/user-management/")


@login_required(login_url="/maia/login/")
def deploy_view(request, group_id):
    if not request.user.is_superuser:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({}, request))

    id_token = request.session.get("oidc_id_token")

    if "BACKEND" in os.environ and os.environ["BACKEND"] == "compose":
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(
            html_template.render({"message": "MAIA is running in Compose mode, Project Deployment is not supported."}, request)
        )
    argocd_cluster_id = settings.ARGOCD_CLUSTER
    argocd_url = settings.ARGOCD_SERVER

    cluster_config_path = os.environ["CLUSTER_CONFIG_PATH"]
    # maia_config_file = os.environ["MAIA_CONFIG_PATH"]
    # config_path=os.environ["CONFIG_PATH"]

    project_form_dict, cluster_id = get_project(group_id, settings=settings, maia_project_model=MAIAProject)

    if cluster_id is None:
        return redirect("/maia/user-management/")

    kubeconfig_dict = generate_kubeconfig(id_token, request.user.username, "default", argocd_cluster_id, settings=settings)
    local_kubeconfig_dict = generate_kubeconfig(id_token, request.user.username, "default", cluster_id, settings=settings)
    config.load_kube_config_from_dict(kubeconfig_dict)

    with open(Path("/tmp").joinpath("kubeconfig-project"), "w") as f:
        yaml.dump(kubeconfig_dict, f)
    with open(Path("/tmp").joinpath("kubeconfig-project-local"), "w") as f:
        yaml.dump(local_kubeconfig_dict, f)
        os.environ["KUBECONFIG"] = str(Path("/tmp").joinpath("kubeconfig-project"))
        os.environ["KUBECONFIG_LOCAL"] = str(Path("/tmp").joinpath("kubeconfig-project-local"))

        cluster_config_dict = yaml.safe_load(Path(cluster_config_path).joinpath(cluster_id + ".yaml").read_text())
        # maia_config_dict = yaml.safe_load(Path(maia_config_file).read_text())

        namespace = project_form_dict["group_ID"].lower().replace("_", "-")

        create_namespace(request=request, cluster_id=cluster_id, namespace_id=namespace, settings=settings)

        if project_form_dict["environment"] != "Base":

            registry_url = os.environ.get("MAIA_PRIVATE_REGISTRY", None)

            if (
                not Path(cluster_config_path).joinpath(f"MAIA-Cloud_MAIA-KTH-{namespace}.json").exists()
                and not Path(cluster_config_path).joinpath("MAIA-Cloud-GLOBAL.json").exists()
            ):
                html_template = loader.get_template("home/page-500.html")
                return HttpResponse(
                    html_template.render(
                        {"message": f"The required JSON key does not exist for the project {namespace}"}, request
                    )
                )

            if Path(cluster_config_path).joinpath("MAIA-Cloud-GLOBAL.json").exists():
                credentials_file = Path(cluster_config_path).joinpath("MAIA-Cloud-GLOBAL.json")
            if Path(cluster_config_path).joinpath(f"MAIA-Cloud_MAIA-KTH-{namespace}.json").exists():
                credentials_file = Path(cluster_config_path).joinpath(f"MAIA-Cloud_MAIA-KTH-{namespace}.json")
            try:
                with open(credentials_file, "r") as f:
                    docker_credentials = json.load(f)
                    username = docker_credentials.get("harbor_username")
                    password = docker_credentials.get("harbor_password")
            except Exception:
                with open(credentials_file, "r") as f:
                    docker_credentials = f.read()
                    username = "_json_key"
                    password = docker_credentials

            config.load_kube_config_from_dict(kubeconfig_dict)
            create_helm_repo_secret_from_context(
                repo_name=f"maia-cloud-ai-{namespace}",
                argocd_namespace="argocd",
                helm_repo_config={
                    "username": username,
                    "password": password,
                    "project": namespace,
                    "url": registry_url,
                    "type": "helm",
                    "name": f"maia-cloud-ai-{namespace}",
                    "enableOCI": "true",
                },
            )

            config.load_kube_config_from_dict(local_kubeconfig_dict)

            create_docker_registry_secret_from_context(
                docker_credentials={
                    "registry": "https://" + registry_url.split("/")[0],
                    "username": username,
                    "password": password,
                },
                namespace=namespace,
                secret_name=registry_url.replace(".", "-").replace("/", "-"),
            )

            # secret_name = registry_url.replace(".","-").replace("/","-").replace(":","-")
            # json_key = retrieve_json_key_for_maia_registry_authentication(request, cluster_id, settings, namespace, secret_name, registry_url)

            # with open(Path("/tmp").joinpath(f"json_key-{namespace}"), "w") as f:
            #    json.dump(json_key, f)
            os.environ["JSON_KEY_PATH"] = str(credentials_file)

        config.load_kube_config_from_dict(kubeconfig_dict)
        os.environ["KUBECONFIG"] = str(Path("/tmp").joinpath("kubeconfig-project"))
        disable_argocd = False
        if "ARGOCD_DISABLED" in os.environ and os.environ["ARGOCD_DISABLED"] == "True":
            disable_argocd = True
        msg = deploy_maia_toolkit_api(
            project_form_dict=project_form_dict,
            # maia_config_dict=maia_config_dict,
            cluster_config_dict=cluster_config_dict,
            config_folder="/config",  # config_path,
            redeploy_enabled=True,
            minimal=(project_form_dict["environment"] == "Base"),
            no_argocd=disable_argocd,
        )

        if msg is not None and msg != "":
            html_template = loader.get_template("home/page-500.html")
            return HttpResponse(html_template.render({"message": msg}, request))

        ## Send User and Project Registration email, ONLY IF THE PROJECT IS NEWLY CREATED

        if disable_argocd:
            return redirect(f"/maia/namespaces/{namespace}")
        return redirect(f"{argocd_url}/applications?proj={namespace}")

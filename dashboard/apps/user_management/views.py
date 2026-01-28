import os
from rest_framework import serializers
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.template import loader
from django.conf import settings
from kubernetes import config
from django.contrib.auth.models import User
from pathlib import Path
from .forms import UserTableForm
import re
from apps.models import MAIAUser, MAIAProject
import json
from MAIA.kubernetes_utils import (
    generate_kubeconfig,
    create_helm_repo_secret_from_context,
    create_docker_registry_secret_from_context,
)
from MAIA.dashboard_utils import (
    update_user_table,
    get_project,
    get_project_argo_status_and_user_table,
    get_pending_projects,
    upload_env_file_to_minio,
)
from MAIA.kubernetes_utils import create_namespace
from rest_framework.response import Response
from types import SimpleNamespace
from MAIA.keycloak_utils import (
    get_user_ids,
    register_users_in_group_in_keycloak,
    get_list_of_groups_requesting_a_user,
    get_list_of_users_requesting_a_group,
    get_groups_for_user,
    remove_user_from_group_in_keycloak,
    get_maia_users_from_keycloak,
    get_groups_in_keycloak,
)
import urllib3
import yaml
from django.shortcuts import redirect
from MAIA_scripts.MAIA_install_project_toolkit import deploy_maia_toolkit_api
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAdminUser
from .services import (
    create_user as create_user_service,
    update_user as update_user_service,
    delete_user as delete_user_service,
    create_group as create_group_service,
    delete_group as delete_group_service,
)
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from loguru import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
DNS_LABEL_REGEX = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"


def group_id_validator(value):

    if len(value) > 63:
        raise serializers.ValidationError("Group ID must be at most 63 characters long (Kubernetes namespace limit).")
    if not re.match(DNS_LABEL_REGEX, value):
        raise serializers.ValidationError(
            "Group ID must conform to Kubernetes namespace rules: "
            "lowercase alphanumeric characters or '-', start and end with alphanumeric."
        )
    return value


def namespace_validator(value):
    namespaces = [ns.strip() for ns in value.split(",") if ns.strip()]
    for ns in namespaces:
        if len(ns) > 63:
            raise serializers.ValidationError("Each namespace must be at most 63 characters long (Kubernetes namespace limit).")
        if not re.match(DNS_LABEL_REGEX, ns):
            raise serializers.ValidationError(
                "Each namespace must conform to Kubernetes namespace rules: "
                "lowercase alphanumeric characters or '-', start and end with alphanumeric."
            )
    return ",".join(namespaces)


class UpdateUserSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    namespace = serializers.CharField(max_length=1000, allow_blank=False, trim_whitespace=True)

    def validate_namespace(self, value):
        return namespace_validator(value)


class CreateUserSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    username = serializers.CharField(max_length=150)
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=150)
    namespace = serializers.CharField(max_length=1000, allow_blank=True, trim_whitespace=True)

    def validate_namespace(self, value):
        return namespace_validator(value)


class CreateGroupSerializer(serializers.Serializer):
    group_id = serializers.CharField(max_length=63)
    gpu = serializers.CharField(max_length=100)
    date = serializers.DateField()
    memory_limit = serializers.CharField(max_length=100)
    cpu_limit = serializers.CharField(max_length=100)
    env_file = serializers.FileField(required=False, allow_empty_file=True)
    cluster = serializers.CharField(max_length=100)
    project_tier = serializers.CharField(max_length=100)
    user_id = serializers.EmailField(max_length=254, required=False, allow_blank=True)
    email_list = serializers.ListField(child=serializers.EmailField(), required=False, allow_empty=True)
    description = serializers.CharField(max_length=5000, required=False, allow_blank=True, allow_null=True)
    supervisor = serializers.EmailField(max_length=254, required=False, allow_blank=True, allow_null=True)

    def validate_group_id(self, value):
        return group_id_validator(value)


class DeleteGroupSerializer(serializers.Serializer):
    group_id = serializers.CharField(max_length=63)

    def validate_group_id(self, value):
        return group_id_validator(value)


class EmailPathSerializer(serializers.Serializer):
    email = serializers.EmailField()


class UserManagementAPIListPendingGroupsView(APIView):
    throttle_classes = [UserRateThrottle]
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        pending_groups = get_pending_projects(settings=settings, maia_project_model=MAIAProject)
        return Response({"pending_groups": pending_groups}, status=200)


class UserManagementAPIListGroupsView(APIView):
    throttle_classes = [UserRateThrottle]
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        groups = MAIAProject.objects.all().values(
            "id",
            "namespace",
            "gpu",
            "date",
            "memory_limit",
            "cpu_limit",
            "env_file",
            "cluster",
            "project_tier",
            "email",
            "description",
            "supervisor",
        )
        keycloak_groups = {v: k for k, v in get_groups_in_keycloak(settings=settings).items()}
        # Fetch all Keycloak users once and build a mapping from group_id to users
        keycloak_users = get_maia_users_from_keycloak(settings=settings)
        group_users = {}
        for user in keycloak_users:
            for group_id in user.get("groups", []):
                group_users.setdefault(group_id, []).append(user)
        for group in groups:
            namespace = group["namespace"]
            group["group_registered_in_keycloak"] = namespace in keycloak_groups
            if group["group_registered_in_keycloak"]:
                group["users_in_keycloak"] = [user["email"] for user in group_users.get("MAIA:" + namespace, [])]
            else:
                group["users_in_keycloak"] = []
        return Response({"groups": groups}, status=200)


class UserManagementAPIListUsersView(APIView):
    permission_classes = [IsAdminUser]
    throttle_classes = [UserRateThrottle]

    def get(self, request, *args, **kwargs):
        users_queryset = MAIAUser.objects.all().values("id", "email", "username", "namespace")
        users = list(users_queryset)
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


class UserManagementAPICreateUserView(APIView):
    permission_classes = [IsAdminUser]
    throttle_classes = [UserRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = CreateUserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": serializer.errors}, status=400)

        validated_data = serializer.validated_data
        email = validated_data["email"]
        username = validated_data["username"]
        first_name = validated_data["first_name"]
        last_name = validated_data["last_name"]
        namespace = validated_data["namespace"]
        if not namespace:
            namespace = settings.USERS_GROUP
        result = create_user_service(email, username, first_name, last_name, namespace)
        return Response({"message": result["message"]}, status=result["status"])


class UserManagementAPIUpdateUserView(APIView):
    permission_classes = [IsAdminUser]
    throttle_classes = [UserRateThrottle]

    def patch(self, request, *args, **kwargs):
        serializer = UpdateUserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": serializer.errors}, status=400)

        validated_data = serializer.validated_data
        email = validated_data["email"]
        namespace = validated_data["namespace"]
        result = update_user_service(email, namespace)
        return Response({"message": result["message"]}, status=result["status"])


class UserManagementAPIDeleteUserView(APIView):
    permission_classes = [IsAdminUser]
    throttle_classes = [UserRateThrottle]

    def delete(self, request, *args, **kwargs):
        email = request.query_params.get("email")
        if email is None:
            return Response({"error": {"email": ["This query parameter is required."]}}, status=400)
        serializer = EmailPathSerializer(data={"email": email})
        if not serializer.is_valid():
            # Return a generic bad request error without leaking detailed validation information
            return Response({"error": {"email": ["Invalid email format."]}}, status=400)
        validated_email = serializer.validated_data["email"]
        force_param = request.query_params.get("force", "false")
        force = str(force_param).lower() in ("1", "true", "yes", "on")
        result = delete_user_service(validated_email, force)
        return Response({"message": result["message"]}, status=result["status"])


class UserManagementAPICreateGroupView(APIView):
    permission_classes = [IsAdminUser]
    throttle_classes = [UserRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = CreateGroupSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": serializer.errors}, status=400)

        validated_data = serializer.validated_data
        group_id = validated_data["group_id"]
        gpu = validated_data["gpu"]
        date = validated_data["date"]
        memory_limit = validated_data["memory_limit"]
        cpu_limit = validated_data["cpu_limit"]
        env_file = validated_data["env_file"]
        cluster = validated_data["cluster"]
        project_tier = validated_data["project_tier"]
        user_id = validated_data.get("user_id", None)
        email_list = validated_data.get("email_list", None)
        description = validated_data.get("description", None)
        supervisor = validated_data.get("supervisor", None)
        if request.FILES:
            env_file = request.FILES["env_file"]
            if "MINIO_SECURE" in os.environ:
                if os.environ["MINIO_SECURE"].lower() == "false":
                    secure = False
                elif os.environ["MINIO_SECURE"].lower() == "true":
                    secure = True
                else:
                    secure = os.environ["MINIO_SECURE"]
            else:
                secure = True
            if "MINIO_PUBLIC_SECURE" in os.environ:
                if os.environ["MINIO_PUBLIC_SECURE"].lower() == "false":
                    public_secure = False
                elif os.environ["MINIO_PUBLIC_SECURE"].lower() == "true":
                    public_secure = True
                else:
                    public_secure = os.environ["MINIO_PUBLIC_SECURE"]
            else:
                public_secure = secure
            settings_dict = {
                "MINIO_URL": os.environ["MINIO_URL"],
                "MINIO_PUBLIC_URL": (
                    os.environ["MINIO_PUBLIC_URL"] if "MINIO_PUBLIC_URL" in os.environ else os.environ["MINIO_URL"]
                ),
                "MINIO_PUBLIC_SECURE": public_secure if "MINIO_PUBLIC_SECURE" in os.environ else secure,
                "MINIO_ACCESS_KEY": os.environ["MINIO_ACCESS_KEY"],
                "MINIO_SECRET_KEY": os.environ["MINIO_SECRET_KEY"],
                "MINIO_SECURE": secure,
                "BUCKET_NAME": os.environ["BUCKET_NAME"],
            }
            settings = SimpleNamespace(**settings_dict)
            filename, success = upload_env_file_to_minio(env_file=env_file, namespace=group_id, settings=settings)
            if not success:
                return Response({"error": filename}, status=400)
        env_file = filename
        result = create_group_service(
            group_id,
            gpu,
            date,
            memory_limit,
            cpu_limit,
            env_file,
            cluster,
            project_tier,
            user_id,
            email_list,
            description,
            supervisor,
        )
        return Response({"message": result["message"]}, status=result["status"])


class UserManagementAPIDeleteGroupView(APIView):
    permission_classes = [IsAdminUser]
    throttle_classes = [UserRateThrottle]

    def delete(self, request, group_id, *args, **kwargs):
        serializer = DeleteGroupSerializer(data={"group_id": group_id})
        if not serializer.is_valid():
            return Response({"error": serializer.errors}, status=400)

        validated_data = serializer.validated_data
        group_id = validated_data["group_id"]
        result = delete_group_service(group_id)
        return Response({"message": result["message"]}, status=result["status"])


@method_decorator(csrf_exempt, name="dispatch")  # 🚀 This disables CSRF for this API
class ProjectChartValuesAPIView(APIView):
    permission_classes = [AllowAny]  # 🚀 Allow requests without authentication or CSRF
    throttle_classes = [AnonRateThrottle]

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
                            r_username = docker_credentials.get("username")
                            password = docker_credentials.get("password")
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
    try:
        if not request.user.is_superuser:
            html_template = loader.get_template("home/page-500.html")
            return HttpResponse(html_template.render({}, request))

        argocd_url = settings.ARGOCD_SERVER

        keycloak_users = get_user_ids(settings=settings)

        for keycloak_user in keycloak_users:
            if MAIAUser.objects.filter(email=keycloak_user).exists():
                ...  # do nothing
            else:
                logger.info(f"Creating user: {keycloak_user}")
                try:
                    admin = False
                    if settings.ADMIN_GROUP in keycloak_users[keycloak_user]:
                        admin = True
                    MAIAUser.objects.create(
                        email=keycloak_user,
                        username=keycloak_user,
                        namespace=",".join(keycloak_users[keycloak_user]),
                        is_superuser=admin,
                        is_staff=admin,
                    )
                except Exception:
                    User.objects.filter(email=keycloak_user).delete()
                    admin = False
                    if settings.ADMIN_GROUP in keycloak_users[keycloak_user]:
                        admin = True
                    logger.info(f"Deleting user and creating new MAIA user: {keycloak_user}")
                    MAIAUser.objects.create(
                        email=keycloak_user,
                        username=keycloak_user,
                        namespace=",".join(keycloak_users[keycloak_user]),
                        is_superuser=admin,
                        is_staff=admin,
                    )
                    logger.info(f"User created: {keycloak_user}")
        to_register_in_groups, to_register_in_keycloak, maia_groups_dict, project_argo_status, users_to_remove_from_group = (
            get_project_argo_status_and_user_table(
                settings=settings, request=request, maia_user_model=MAIAUser, maia_project_model=MAIAProject
            )
        )
        for maia_group in maia_groups_dict:
            logger.info(f"MAIA group: {maia_group} {maia_groups_dict[maia_group]}")
            if not MAIAProject.objects.filter(namespace=maia_group).exists():
                users = maia_groups_dict[maia_group]["users"]
                if len(users) == 1:
                    email = users[0]
                    supervisor = email
                else:
                    supervisor = None
                    email = None
                MAIAProject.objects.create(
                    namespace=maia_group,
                    email=email,
                    supervisor=supervisor,
                )

        logger.info("Users to Register in Keycloak: ", to_register_in_keycloak)
        logger.info("Users to Register in Groups: ", to_register_in_groups)
        logger.info("Users to Remove from Group: ", users_to_remove_from_group)

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
    except Exception as e:
        logger.exception(e)


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
            if keycloak_group == settings.ADMIN_GROUP:
                user = MAIAUser.objects.filter(email=email).first()
                user.is_superuser = False
                user.is_staff = False
                user.save()

    return redirect("/maia/user-management/")


@login_required(login_url="/maia/login/")
def delete_group_view(request, group_id):
    if not request.user.is_superuser:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({}, request))

    result = delete_group_service(group_id)

    if result["status"] == 200:
        return redirect("/maia/user-management/")
    else:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({"message": result["message"]}, request))


@login_required(login_url="/maia/login/")
def register_user_view(request, email):
    if not request.user.is_superuser:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({}, request))

    user = MAIAUser.objects.filter(email=email).first()
    if not user:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({"message": "User not found"}, request))
    namespace = user.namespace
    username = user.username
    first_name = user.first_name
    last_name = user.last_name
    if not namespace:
        namespace = settings.USERS_GROUP
    result = create_user_service(email, username, first_name, last_name, namespace)
    if result["status"] == 200:
        return redirect("/maia/user-management/")
    else:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({"message": result["message"]}, request))


@login_required(login_url="/maia/login/")
def delete_user_view(request, email):
    if not request.user.is_superuser:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({}, request))

    result = delete_user_service(email, force=True)
    logger.info(f"Result: {result}")
    if result["status"] == 200:
        return redirect("/maia/user-management/")
    else:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({"message": result["message"]}, request))


@login_required(login_url="/maia/login/")
def register_user_in_group_view(request, email):
    if not request.user.is_superuser:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({}, request))

    groups = get_list_of_groups_requesting_a_user(email=email, user_model=MAIAUser)

    for group_id in groups:
        register_users_in_group_in_keycloak(group_id=group_id, emails=[email], settings=settings)
        if group_id == settings.ADMIN_GROUP:
            user = MAIAUser.objects.filter(email=email).first()
            user.is_superuser = True
            user.is_staff = True
            user.save()

    return redirect("/maia/user-management/")


@login_required(login_url="/maia/login/")
def register_group_view(request, group_id):
    if not request.user.is_superuser:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({}, request))

    project = MAIAProject.objects.filter(namespace=group_id).first()
    if project:
        gpu = project.gpu
        date = project.date
        memory_limit = project.memory_limit
        cpu_limit = project.cpu_limit
        env_file = project.env_file
        cluster = project.cluster
        project_tier = project.project_tier
        user_id = project.email
        description = project.description
        supervisor = project.supervisor
    else:
        gpu = None
        date = None
        memory_limit = None
        cpu_limit = None
        env_file = None
        cluster = None
        project_tier = None
        user_id = None
        email_list = None
        description = None
        supervisor = None
    email_list = get_list_of_users_requesting_a_group(maia_user_model=MAIAUser, group_id=group_id)
    result = create_group_service(
        group_id,
        gpu,
        date,
        memory_limit,
        cpu_limit,
        env_file,
        cluster,
        project_tier,
        user_id,
        email_list,
        description,
        supervisor,
    )

    if result["status"] == 200:
        return redirect("/maia/user-management/")
    else:
        html_template = loader.get_template("home/page-500.html")
        return HttpResponse(html_template.render({"message": result["message"]}, request))


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
                    username = docker_credentials.get("username")
                    password = docker_credentials.get("password")
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
        cluster_config_dict["ssh_port_type"] = "LoadBalancer"
        # cluster_config_dict["maia_metallb_ip"] = ""
        cluster_config_dict["metallb_shared_ip"] = "traefik"
        cluster_config_dict["metallb_ip_pool"] = "default-addresspool"
        cluster_config_dict["port_range"] = [2022, 2122]
        cluster_config_dict["shared_storage_class"] = "microk8s-hostpath"
        cluster_config_dict["storage_class"] = "microk8s-hostpath"
        cluster_config_dict["domain"] = "maia.io"
        cluster_config_dict["url_type"] = "subdomain"
        cluster_config_dict["argocd_destination_cluster_address"] = "https://kubernetes.default.svc"
        cluster_config_dict["radiology-cluster-config"] = {
            "ip_whitelist": [
                # "83.251.104.145/32",
                # "130.237.84.121/32",
                "10.0.2.2/32"
            ],
            "env": {"maia_workspace_version": "1.7.1"},
            "allow_ssh_password_authentication": "True",
        }
        os.environ["maia_project_chart"] = "maia-project"
        os.environ["maia_project_repo"] = "https://minnelab.github.io/MAIA/"
        os.environ["maia_project_version"] = "1.8.0"
        os.environ["argocd_namespace"] = "argocd"
        argocd_url = "https://argocd.maia.io"
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

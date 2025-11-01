import os
from django.http import FileResponse
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
from MAIA.kubernetes_utils import generate_kubeconfig, retrieve_json_key_for_maia_registry_authentication, create_helm_repo_secret_from_context, create_docker_registry_secret_from_context
from MAIA.dashboard_utils import update_user_table, get_project, get_project_argo_status_and_user_table
from MAIA.kubernetes_utils import create_namespace
from rest_framework.response import Response
from MAIA.keycloak_utils import get_user_ids, register_user_in_keycloak, register_group_in_keycloak, register_users_in_group_in_keycloak, get_list_of_groups_requesting_a_user, get_list_of_users_requesting_a_group, delete_group_in_keycloak, get_groups_for_user, remove_user_from_group_in_keycloak
import urllib3
import yaml
from django.shortcuts import redirect
from MAIA_scripts.MAIA_install_project_toolkit import deploy_maia_toolkit_api
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
@method_decorator(csrf_exempt, name='dispatch')  # 🚀 This disables CSRF for this API
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
            #maia_config_file = os.environ["MAIA_CONFIG_PATH"]


            kubeconfig_dict = generate_kubeconfig(id_token, username, "default", argocd_cluster_id, settings=settings)
            local_kubeconfig_dict = generate_kubeconfig(id_token, username, "default", cluster_id, settings=settings)
            config.load_kube_config_from_dict(kubeconfig_dict)
            
            with open(Path("/tmp").joinpath("kubeconfig-project"), "w") as f:
                yaml.dump(kubeconfig_dict, f)
            with open(Path("/tmp").joinpath("kubeconfig-project-local"), "w") as f:
                yaml.dump(local_kubeconfig_dict, f)
                os.environ["KUBECONFIG"] = str(Path("/tmp").joinpath("kubeconfig-project"))
                os.environ["KUBECONFIG_LOCAL"] = str(Path("/tmp").joinpath("kubeconfig-project-local"))
            
            

                cluster_config_dict = yaml.safe_load(Path(cluster_config_path).joinpath(cluster_id+".yaml").read_text())
                #maia_config_dict = yaml.safe_load(Path(maia_config_file).read_text())

                namespace = project_form_dict["group_ID"].lower().replace("_", "-")
                
                if project_form_dict["environment"] != "Base":
                    registry_url = os.environ.get("MAIA_PRIVATE_REGISTRY", None)
                    if not Path(cluster_config_path).joinpath(f"MAIA-Cloud_MAIA-KTH-{namespace}.json").exists() and not Path(cluster_config_path).joinpath(f"MAIA-Cloud-GLOBAL.json").exists():
                        html_template = loader.get_template('home/page-500.html')
                        return HttpResponse(html_template.render({"message": f"The required JSON key does not exist for the project {namespace}"}, request))
                    
                    if Path(cluster_config_path).joinpath(f"MAIA-Cloud-GLOBAL.json").exists():
                        credentials_file = Path(cluster_config_path).joinpath(f"MAIA-Cloud-GLOBAL.json")
                    if Path(cluster_config_path).joinpath(f"MAIA-Cloud_MAIA-KTH-{namespace}.json").exists():
                        credentials_file = Path(cluster_config_path).joinpath(f"MAIA-Cloud_MAIA-KTH-{namespace}.json")
                    try:
                        with open(credentials_file, "r") as f:
                            docker_credentials = json.load(f)
                            r_username = docker_credentials.get("harbor_username")
                            password = docker_credentials.get("harbor_password")
                    except:
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
                    secret_name=registry_url.replace(".", "-").replace("/", "-")
                    )
                    os.environ["JSON_KEY_PATH"] = str(credentials_file)
                    
                config.load_kube_config_from_dict(kubeconfig_dict)
                os.environ["KUBECONFIG"] = str(Path("/tmp").joinpath("kubeconfig-project"))
                disable_argocd = True
                response = deploy_maia_toolkit_api(project_form_dict=project_form_dict, 
                                        #maia_config_dict=maia_config_dict,
                                        cluster_config_dict=cluster_config_dict,
                                        config_folder="/config", #config_path,
                                        redeploy_enabled=True,
                                        minimal=(project_form_dict["environment"] == "Base"),
                                        no_argocd=disable_argocd,
                                        return_values_only=True
                                        )
                return Response({"project_values": response}, status=200)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

# Create your views here.
@login_required(login_url="/maia/login/")
def index(request):
    if not request.user.is_superuser:
        html_template = loader.get_template('home/page-500.html')
        return HttpResponse(html_template.render({}, request))
    
    argocd_url = settings.ARGOCD_SERVER

    keycloak_users = get_user_ids(settings=settings)
    
    for keycloak_user in keycloak_users:
        if User.objects.filter(email=keycloak_user).exists():
            ... # do nothing
        else:
            MAIAUser.objects.create(email=keycloak_user, username=keycloak_user, namespace=",".join(keycloak_users[keycloak_user]))

    to_register_in_groups, to_register_in_keycloak, maia_groups_dict, project_argo_status, users_to_remove_from_group = get_project_argo_status_and_user_table(settings=settings, request=request, maia_user_model=MAIAUser, maia_project_model=MAIAProject)   
    
    print("Users to Register in Keycloak: ", to_register_in_keycloak)
    print("Users to Register in Groups: ", to_register_in_groups)
    print("Users to Remove from Group: ", users_to_remove_from_group)

    if request.method == "POST":
        

        user_list = list(MAIAUser.objects.all().values())

        for user in user_list:
            if user['email'] in to_register_in_keycloak:
                user['is_registered_in_keycloak'] = 0
            else:
                user['is_registered_in_keycloak'] = 1
            if user['email'] in to_register_in_groups:
                user['is_registered_in_groups'] = to_register_in_groups[user['email']]
            else:
                user['is_registered_in_groups'] = 1
            if user["email"] in users_to_remove_from_group:
                user["remove_from_group"] = users_to_remove_from_group[user["email"]]
            else:
                user["remove_from_group"] = 0

        # Sort users: put at the beginning if user needs action (not registered in keycloak, needs group registration, or needs removal from group)
        sorted_user_list = sorted(
            user_list,
            key=lambda x: not (
                x['is_registered_in_keycloak'] == 0
                or x['is_registered_in_groups'] is not 1
                or x['remove_from_group'] is not 0
            )
        )
        if "BACKEND" in os.environ:
            backend = os.environ["BACKEND"]
        else:
            backend = "default"
        context = {
            "BACKEND": backend,
            "user_table": sorted_user_list,
            "minio_console_url": os.environ.get("MINIO_CONSOLE_URL",None),
            "maia_groups_dict": maia_groups_dict,
            "form": UserTableForm(request.POST),
            "project_argo_status": project_argo_status,
            "argocd_url": argocd_url,
            "user": ["admin"],
            "username": request.user.username + " [ADMIN]"
        }
        html_template = loader.get_template('base_user_management.html')

        form = UserTableForm(request.POST)

        if form.is_valid():
            update_user_table(form, User, MAIAUser, MAIAProject)
        else:
            ...
            #update_user_table(form, User, MAIAUser, MAIAProject)

        return HttpResponse(html_template.render(context, request))

    
    user_list = list(MAIAUser.objects.all().values())


    for user in user_list:
        if user['email'] in to_register_in_keycloak:
            user['is_registered_in_keycloak'] = 0
        else:
            user['is_registered_in_keycloak'] = 1
        if user['email'] in to_register_in_groups:
            user['is_registered_in_groups'] = to_register_in_groups[user['email']]
        else:
            user['is_registered_in_groups'] = 1
        if user["email"] in users_to_remove_from_group:
            user["remove_from_group"] = users_to_remove_from_group[user["email"]]
        else:
            user["remove_from_group"] = 0

    # Sort users: put at the beginning if user needs action (not registered in keycloak, needs group registration, or needs removal from group)
    sorted_user_list = sorted(
        user_list,
        key=lambda x: not (
            x['is_registered_in_keycloak'] == 0
            or x['is_registered_in_groups'] is not 1
            or x['remove_from_group'] is not 0
        )
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
        "minio_console_url": os.environ.get("MINIO_CONSOLE_URL",None),
        "form": user_form,
        "user": ["admin"],
        "project_argo_status": project_argo_status,
        "argocd_url": argocd_url,
        "username": request.user.username + " [ADMIN]"
    }

    html_template = loader.get_template('base_user_management.html')
    if not request.user.is_superuser:
        html_template = loader.get_template('home/page-500.html')
        return HttpResponse(html_template.render({}, request))


    return HttpResponse(html_template.render(context, request))


@login_required(login_url="/maia/login/")
def remove_user_from_group_view(request, email):
    if not request.user.is_superuser:
        html_template = loader.get_template('home/page-500.html')
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
        html_template = loader.get_template('home/page-500.html')
        return HttpResponse(html_template.render({}, request))

    delete_group_in_keycloak(group_id=group_id, settings=settings)
    
    MAIAProject.objects.filter(namespace=group_id).delete()
    
    return redirect("/maia/user-management/")

@login_required(login_url="/maia/login/")
def register_user_view(request, email):
    if not request.user.is_superuser:
        html_template = loader.get_template('home/page-500.html')
        return HttpResponse(html_template.render({}, request))

    register_user_in_keycloak(email=email, settings=settings)

    return redirect("/maia/user-management/")

@login_required(login_url="/maia/login/")
def register_user_in_group_view(request, email):
    if not request.user.is_superuser:
        html_template = loader.get_template('home/page-500.html')
        return HttpResponse(html_template.render({}, request))
    


    groups = get_list_of_groups_requesting_a_user(email=email, user_model=MAIAUser)
    
    for group_id in groups:
        register_users_in_group_in_keycloak(group_id=group_id,emails=[email], settings=settings)

    return redirect("/maia/user-management/")

@login_required(login_url="/maia/login/")
def register_group_view(request, group_id):
    if not request.user.is_superuser:
        html_template = loader.get_template('home/page-500.html')
        return HttpResponse(html_template.render({}, request))
    


    register_group_in_keycloak(group_id=group_id, settings=settings)
    emails = get_list_of_users_requesting_a_group(maia_user_model=MAIAUser, group_id=group_id)

    register_users_in_group_in_keycloak(group_id=group_id,emails=emails, settings=settings)

    return redirect("/maia/user-management/")


@login_required(login_url="/maia/login/")
def deploy_view(request, group_id):
    if not request.user.is_superuser:
        html_template = loader.get_template('home/page-500.html')
        return HttpResponse(html_template.render({}, request))

    id_token = request.session.get('oidc_id_token')

    if "BACKEND" in os.environ and os.environ["BACKEND"] == "compose":
        html_template = loader.get_template('home/page-500.html')
        return HttpResponse(html_template.render({"message": "MAIA is running in Compose mode, Project Deployment is not supported."}, request))
    argocd_cluster_id = settings.ARGOCD_CLUSTER
    argocd_url = settings.ARGOCD_SERVER


    cluster_config_path = os.environ["CLUSTER_CONFIG_PATH"]
    #maia_config_file = os.environ["MAIA_CONFIG_PATH"]
    #config_path=os.environ["CONFIG_PATH"]

    
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
    
    

        cluster_config_dict = yaml.safe_load(Path(cluster_config_path).joinpath(cluster_id+".yaml").read_text())
        #maia_config_dict = yaml.safe_load(Path(maia_config_file).read_text())

        namespace = project_form_dict["group_ID"].lower().replace("_", "-")
        
        create_namespace(request=request, cluster_id=cluster_id, namespace_id=namespace, settings=settings)

        if project_form_dict["environment"] != "Base":

            registry_url = os.environ.get("MAIA_PRIVATE_REGISTRY", None)

            if not Path(cluster_config_path).joinpath(f"MAIA-Cloud_MAIA-KTH-{namespace}.json").exists() and not Path(cluster_config_path).joinpath(f"MAIA-Cloud-GLOBAL.json").exists():
                html_template = loader.get_template('home/page-500.html')
                return HttpResponse(html_template.render({"message": f"The required JSON key does not exist for the project {namespace}"}, request))
            
            if Path(cluster_config_path).joinpath(f"MAIA-Cloud-GLOBAL.json").exists():
                credentials_file = Path(cluster_config_path).joinpath(f"MAIA-Cloud-GLOBAL.json")
            if Path(cluster_config_path).joinpath(f"MAIA-Cloud_MAIA-KTH-{namespace}.json").exists():
                credentials_file = Path(cluster_config_path).joinpath(f"MAIA-Cloud_MAIA-KTH-{namespace}.json")
            try:
                with open(credentials_file, "r") as f:
                    docker_credentials = json.load(f)
                    username = docker_credentials.get("harbor_username")
                    password = docker_credentials.get("harbor_password")
            except:
                with open(credentials_file, "r") as f:
                    docker_credentials = f.read()
                    username = "_json_key"
                    password = docker_credentials
          
            config.load_kube_config_from_dict(kubeconfig_dict)
            create_helm_repo_secret_from_context(
                repo_name=f"maia-cloud-ai-{namespace}",
                argocd_namespace = "argocd",
                helm_repo_config={
                    "username": username,
        
                    "password": password,
                    "project": namespace,
                    "url": registry_url,
                    "type": "helm",
                    "name": f"maia-cloud-ai-{namespace}",
                    "enableOCI": "true"
                }
            )
        
            config.load_kube_config_from_dict(local_kubeconfig_dict)
  
            create_docker_registry_secret_from_context(
            docker_credentials={
                "registry": "https://" +registry_url.split("/")[0],
                "username": username,
                "password": password,
                
            },
            namespace=namespace,
            secret_name=registry_url.replace(".", "-").replace("/", "-")
            )
            

            #secret_name = registry_url.replace(".","-").replace("/","-").replace(":","-")
            #json_key = retrieve_json_key_for_maia_registry_authentication(request, cluster_id, settings, namespace, secret_name, registry_url)
            
            #with open(Path("/tmp").joinpath(f"json_key-{namespace}"), "w") as f:
            #    json.dump(json_key, f)
            os.environ["JSON_KEY_PATH"] = str(credentials_file)
            
        config.load_kube_config_from_dict(kubeconfig_dict)
        os.environ["KUBECONFIG"] = str(Path("/tmp").joinpath("kubeconfig-project"))
        disable_argocd = False
        if "ARGOCD_DISABLED" in os.environ and os.environ["ARGOCD_DISABLED"] == "True":
            disable_argocd = True
        msg = deploy_maia_toolkit_api(project_form_dict=project_form_dict, 
                                #maia_config_dict=maia_config_dict,
                                cluster_config_dict=cluster_config_dict,
                                config_folder="/config", #config_path,
                                redeploy_enabled=True,
                                minimal=(project_form_dict["environment"] == "Base"),
                                no_argocd=disable_argocd,
                                )
        
        if msg is not None and msg != "":
            html_template = loader.get_template('home/page-500.html')
            return HttpResponse(html_template.render({"message": msg}, request))
    
        ## Send User and Project Registration email, ONLY IF THE PROJECT IS NEWLY CREATED
        
        if  disable_argocd:
            return redirect(f"/maia/namespaces/{namespace}")
        return redirect(f"{argocd_url}/applications?proj={namespace}")


    
# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

# Create your views here.
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from .forms import LoginForm, SignUpForm, RegisterProjectForm, MAIAInfoForm
from minio import Minio
from MAIA.dashboard_utils import send_discord_message, verify_minio_availability, send_maia_info_email
from MAIA.kubernetes_utils import get_minio_shareable_link
from core.settings import GITHUB_AUTH
from django.conf import settings
from apps.models import MAIAUser, MAIAProject
import os


def login_view(request):
    form = LoginForm(request.POST or None)

    msg = None

    if request.method == "POST":

        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect("/")
            else:
                msg = "Invalid credentials"
        else:
            msg = "Error validating the form"

    backend = "default"
    if "BACKEND" in os.environ:
        backend = os.environ["BACKEND"]
    return render(
        request,
        "accounts/login.html",
        {
            "BACKEND": backend,
            "dashboard_version": settings.DASHBOARD_VERSION,
            "form": form,
            "msg": msg,
            "GITHUB_AUTH": GITHUB_AUTH,
        },
    )


def register_user(request):
    msg = None
    success = False

    if request.method == "POST":

        form = SignUpForm(request.POST, request.FILES)
        if form.is_valid():

            namespace = form.cleaned_data.get("namespace")
            if namespace.endswith(" (Pending)"):
                namespace = namespace[: -len(" (Pending)")]
            form.instance.namespace = namespace + ",users"
            form.save()
            username = form.cleaned_data.get("username")
            raw_password = form.cleaned_data.get("password1")
            namespace = form.cleaned_data.get("namespace")

            user = authenticate(username=username, password=raw_password)

            user.is_active = False
            user.save()

            # if os.environ["DEBUG"] != "True":
            # send_email(email, os.environ["admin_email"], email)
            if settings.DISCORD_URL is not None:
                send_discord_message(username=username, namespace=namespace, url=settings.DISCORD_URL)
            msg = "Request for Account Registration submitted successfully. Please wait for the admin to approve your request."
            success = True

            # return redirect("/login/")

        else:
            print(form.errors)
            if "username" in form.errors and any("already exists" in str(e) for e in form.errors["username"]):
                requested_namespace = form.cleaned_data.get("namespace")
                user_in_db = MAIAUser.objects.filter(email=form.cleaned_data.get("email")).first()
                namespace_is_already_registered = False
                if user_in_db:
                    user_id = user_in_db.id
                    namespace = user_in_db.namespace
                    for ns in namespace.split(","):
                        if ns == requested_namespace:
                            namespace_is_already_registered = True
                    if not namespace_is_already_registered:
                        namespace = f"{namespace},{requested_namespace}"
                        MAIAUser.objects.filter(id=user_id).update(namespace=namespace)
                        msg = "A user with that email already exists. {} has now requested to be registered to the project {}".format(
                            form.cleaned_data.get("email"), form.cleaned_data.get("namespace")
                        )
                        if settings.DISCORD_URL is not None:
                            send_discord_message(
                                username=form.cleaned_data.get("email"), namespace=namespace, url=settings.DISCORD_URL
                            )
                        success = True
                    else:
                        msg = "A user with that username already exists and has been already registered to the project {}".format(
                            form.cleaned_data.get("namespace")
                        )
                        success = True
                else:
                    msg = "A user with that username does not exist."
            else:
                msg = "Form is not valid"
    else:
        form = SignUpForm()

    return render(
        request,
        "accounts/register.html",
        {"dashboard_version": settings.DASHBOARD_VERSION, "form": form, "msg": msg, "success": success},
    )


@login_required(login_url="/maia/login/")
def send_maia_email(request):

    if not request.user.is_superuser:
        return redirect("/maia/")

    hostname = settings.HOSTNAME
    register_project_url = f"https://{hostname}/maia/register_project/"
    register_user_url = f"https://{hostname}/maia/register/"
    discord_support_link = settings.DISCORD_SUPPORT_URL
    msg = None
    success = False

    if request.method == "POST":

        form = MAIAInfoForm(request.POST, request.FILES)
        if form.is_valid():
            send_maia_info_email(form.cleaned_data.get("email"), register_project_url, register_user_url, discord_support_link)
            msg = "Request for MAIA Info submitted successfully."
            success = True

            # return redirect("/login/")

        else:
            print(form.errors)
            msg = "Form is not valid"
    else:
        form = MAIAInfoForm()

    return render(
        request,
        "accounts/send_maia_info.html",
        {"dashboard_version": settings.DASHBOARD_VERSION, "form": form, "msg": msg, "success": success},
    )


def register_project(request):
    msg = None
    success = False

    minio_available = verify_minio_availability(settings=settings)
    if request.method == "POST":

        form = RegisterProjectForm(request.POST, request.FILES)
        if form.is_valid():

            form.save()
            email = form.cleaned_data.get("email")
            namespace = form.cleaned_data.get("namespace")
            supervisor = form.cleaned_data.get("supervisor")
            project = MAIAProject.objects.filter(namespace=namespace).first()
            if supervisor:
                current_project_admin = MAIAUser.objects.filter(email=project.email).first()
                if current_project_admin.exists():
                    current_namespace = current_project_admin.namespace
                    if namespace not in current_namespace:
                        namespace = f"{current_namespace},{namespace}"
                        current_project_admin.namespace = namespace
                        current_project_admin.save()
                project.email = supervisor
                project.save()

            if not minio_available:
                print("MinIO is not available, skipping conda env storage")
                msg = "Request for Project Registration submitted successfully. Note: MinIO is not available, skipping conda env storage."
                success = True
                return render(
                    request,
                    "accounts/register_project.html",
                    {
                        "dashboard_version": settings.DASHBOARD_VERSION,
                        "minio_available": minio_available,
                        "form": form,
                        "msg": msg,
                        "success": success,
                    },
                )

            if "conda" in request.FILES and minio_available:
                conda_file = request.FILES["conda"]
                if conda_file.name.endswith(".zip"):
                    client = Minio(
                        settings.MINIO_URL,
                        access_key=settings.MINIO_ACCESS_KEY,
                        secret_key=settings.MINIO_SECRET_KEY,
                        secure=settings.MINIO_SECURE,
                    )
                    with open(f"/tmp/{namespace}_env.zip", "wb+") as destination:
                        for chunk in request.FILES["conda"].chunks():
                            destination.write(chunk)
                    print(f"Storing {namespace}_env.zip in MinIO, in bucket {settings.BUCKET_NAME}")
                    client.fput_object(settings.BUCKET_NAME, f"{namespace}_env.zip", f"/tmp/{namespace}_env.zip")
                    print(get_minio_shareable_link(f"{namespace}_env.zip", settings.BUCKET_NAME, settings))
                else:
                    with open(f"/tmp/{namespace}_env", "wb+") as destination:
                        for chunk in request.FILES["conda"].chunks():
                            destination.write(chunk)
                    print(f"Storing {namespace}_env in MinIO, in bucket {settings.BUCKET_NAME}")
                    client.fput_object(settings.BUCKET_NAME, f"{namespace}_env", f"/tmp/{namespace}_env")
                    print(get_minio_shareable_link(f"{namespace}_env", settings.BUCKET_NAME, settings))

            if settings.DISCORD_URL is not None:
                send_discord_message(username=email, namespace=namespace, url=settings.DISCORD_URL, project_registration=True)
            msg = "Request for Project Registration submitted successfully."
            success = True

            # check_pending_projects_and_assign_id(settings=settings)

            # return redirect("/login/")

        else:
            print(form.errors)
            msg = "Form is not valid"
    else:
        form = RegisterProjectForm()

    return render(
        request,
        "accounts/register_project.html",
        {
            "dashboard_version": settings.DASHBOARD_VERSION,
            "minio_available": minio_available,
            "form": form,
            "msg": msg,
            "success": success,
        },
    )

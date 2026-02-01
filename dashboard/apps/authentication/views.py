# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

# Create your views here.
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from .forms import LoginForm, SignUpForm, RegisterProjectForm, MAIAInfoForm
from MAIA.dashboard_utils import send_discord_message, verify_minio_availability, send_maia_info_email, upload_env_file_to_minio
from core.settings import GITHUB_AUTH
from django.conf import settings
from apps.models import MAIAUser, MAIAProject
import os
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from loguru import logger


class RegisterAnonThrottle(AnonRateThrottle):
    scope = "post_anon"


class RegisterUserThrottle(UserRateThrottle):
    scope = "post_user"


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


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([RegisterAnonThrottle, RegisterUserThrottle])
def register_user_api(request):
    return register_user(request, api=True)


def register_user(request, api=False):
    msg = None
    success = False

    if request.method == "POST":
        request_data = request.POST
        request_files = request.FILES
        if api:
            request_data = request.data
            request_files = None
        form = SignUpForm(request_data, request_files)
        if form.is_valid():

            namespace = form.cleaned_data.get("namespace")
            if not namespace:
                namespace = settings.USERS_GROUP
            if namespace.endswith(" (Pending)"):
                namespace = namespace[: -len(" (Pending)")]
            if settings.USERS_GROUP not in namespace:
                form.instance.namespace = f"{namespace},{settings.USERS_GROUP}"
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
            if "username" in form.errors and any("already exists" in str(e) for e in form.errors["username"]):
                requested_namespace = form.cleaned_data.get("namespace")
                if not requested_namespace:
                    requested_namespace = settings.USERS_GROUP
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
                            form.cleaned_data.get("email"), requested_namespace
                        )
                        if settings.DISCORD_URL is not None:
                            send_discord_message(
                                username=form.cleaned_data.get("email"), namespace=namespace, url=settings.DISCORD_URL
                            )
                        success = True
                    else:
                        msg = "A user with that email already exists and has been already registered to the project {}".format(
                            requested_namespace
                        )
                        success = True
                else:
                    msg = "A user with that email does not exist."
                    success = False
            else:
                msg = "Form is not valid: " + str(form.errors)
                success = False
    else:
        form = SignUpForm()

    if api:
        return Response({"msg": msg, "success": success}, status=status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST)
    else:
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
            logger.error(form.errors)
            msg = "Form is not valid"
    else:
        form = MAIAInfoForm()

    return render(
        request,
        "accounts/send_maia_info.html",
        {"dashboard_version": settings.DASHBOARD_VERSION, "form": form, "msg": msg, "success": success},
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([RegisterAnonThrottle, RegisterUserThrottle])
def register_project_api(request):
    return register_project(request, api=True)


def get_or_create_user_in_database(email: str, namespace: str, username: str = None) -> MAIAUser:
    """
    Get or create a MAIAUser by email. Username is only set when creating;
    if not provided, email is used (backward compatibility).
    """
    if not email or not namespace:
        return None
    # Use email as username when not provided (username and email can differ)
    django_username = username if username is not None and username.strip() else email
    if not MAIAUser.objects.filter(email=email).exists():
        if namespace != settings.USERS_GROUP:
            if namespace != "":
                MAIAUser.objects.create(
                    email=email, namespace=f"{namespace},{settings.USERS_GROUP}", username=django_username
                )
            else:
                MAIAUser.objects.create(email=email, namespace=settings.USERS_GROUP, username=django_username)
        else:
            MAIAUser.objects.create(email=email, namespace=namespace, username=django_username)
        return MAIAUser.objects.filter(email=email).first()
    else:
        user = MAIAUser.objects.filter(email=email).first()
        user_namespaces = user.namespace.split(",")
        if namespace not in user_namespaces:
            user_namespaces.append(namespace)
            if "" in user_namespaces:
                user_namespaces.remove("")
            user.namespace = ",".join(user_namespaces)
            user.save()
        return user


def register_project(request, api=False):
    msg = None
    success = False

    minio_available = verify_minio_availability(settings=settings)
    if request.method == "POST":
        request_data = request.POST
        request_files = request.FILES
        if api:
            request_data = request.data
            request_files = request.FILES
        form = RegisterProjectForm(request_data, request_files)
        if form.is_valid():
            form.save()
            email = form.cleaned_data.get("email")
            namespace = form.cleaned_data.get("namespace")
            supervisor = form.cleaned_data.get("supervisor")
            project = MAIAProject.objects.filter(namespace=namespace).first()
            if project:
                get_or_create_user_in_database(email=project.email, namespace=namespace)
                if supervisor:
                    get_or_create_user_in_database(email=supervisor, namespace=namespace)
                if "email_list" in request_data:
                    email_list = request_data.get("email_list")
                    if email_list:
                        for email in email_list.split(","):
                            get_or_create_user_in_database(email=email, namespace=namespace)
            try:
                if "env_file" in request_files and minio_available:
                    env_file = request_files["env_file"]
                    msg, success = upload_env_file_to_minio(env_file, namespace, settings)
            except Exception as e:
                logger.exception(e)
                msg = "Error storing environment file in MinIO"
                success = False

            if settings.DISCORD_URL is not None:
                send_discord_message(username=email, namespace=namespace, url=settings.DISCORD_URL, project_registration=True)
            msg = "Request for Project Registration submitted successfully."
            success = True

            # check_pending_projects_and_assign_id(settings=settings)

            # return redirect("/login/")

        else:
            msg = "Form is not valid: " + str(form.errors)
            success = False
    else:
        form = RegisterProjectForm()

    if api:
        return Response({"msg": msg, "success": success}, status=status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST)
    else:
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

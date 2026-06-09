# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.urls import path, include
from rest_framework.authtoken.views import obtain_auth_token
from .views import login_view, register_user, register_project, send_maia_email, register_project_api, register_user_api
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path("login/jwt/", view=obtain_auth_token),
    path("send_email/", view=send_maia_email, name="send_maia_email"),
    path("login/", login_view, name="login"),
    path("register/", register_user, name="register"),
    path("api/register/", register_user_api, name="register_user_api"),
    path("register_project/", register_project, name="register_project"),
    path("api/register_project/", register_project_api, name="register_project_api"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("social_login/", include("allauth.urls")),
    path("oidc/", include("mozilla_django_oidc.urls")),
]

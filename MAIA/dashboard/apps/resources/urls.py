# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.urls import path
from apps.resources import views

urlpatterns = [
    # The home page
    path("", views.search_resources, name="search"),
    path("resources_status/", views.get_resources_status, name="get_resources_status"),
    path("gpu_status_summary/", views.get_gpu_status_summary, name="get_gpu_status_summary"),
    path("delete_expired_pod/<str:namespace>/<str:pod_name>/", views.delete_expired_pod, name="delete_expired_pod"),
]

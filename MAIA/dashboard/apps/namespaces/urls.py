# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.urls import path
from apps.namespaces import views

urlpatterns = [
    # The home page
    path("<str:namespace_id>", views.namespace_view),
    # path('<str:namespace_id>/web_ssh/<str:path>/',views.ssh_namespace_view),
]

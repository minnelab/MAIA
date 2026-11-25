# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.urls import path, re_path
from apps.home import views

urlpatterns = [
    path("info", views.maia_docs, name="maia_docs"),
    # The home page
    path("", views.index_view, name="home"),
    path("spotlight", views.maia_spotlight, name="spotlight"),
    # Matches any html file
    re_path(r"^.*\.*", views.pages, name="pages"),
]

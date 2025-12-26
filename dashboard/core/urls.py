# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.contrib import admin
from django.urls import path, include  # add this
from django.shortcuts import redirect

urlpatterns = [
    path("", lambda request: redirect("maia/", permanent=True)),
    path("admin/", admin.site.urls),
    path("maia/resources/", include("apps.resources.urls")),
    path("maia/user-management/", include("apps.user_management.urls")),  # path('app',include("apps.deploy_app.urls")),
    path("maia/gpu-booking/", include("apps.gpu_scheduler.urls")),  # Generic Routing
    path("maia/maia-segmentation-portal/", include("apps.maia_segmentation_portal.urls")),  # Segmentation Portal
    # path('deploy',include("apps.deploy.urls")),
    path("maia/namespaces/", include("apps.namespaces.urls")),
    # Django admin route
    path("maia/", include("apps.authentication.urls")),  # Auth routes - login / register
    # ADD NEW Routes HERE
    path("api/", include("apps.api.urls")),  # API Generator Routes
    path("", include("apps.dyn_datatables.urls")),  # Dynamic DB Routes
    # Leave `Home.Urls` as last the last line
    path("maia/", include("apps.home.urls")),  # Generic Routing
    path("maia-api/", include("apps.gpu_scheduler.urls")),  # Generic Routing
]

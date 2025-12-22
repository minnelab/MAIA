# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.urls import path
from apps.user_management import views
from apps.user_management.views import ProjectChartValuesAPIView, UserManagementAPIView

urlpatterns = [
    # The home page
    path("", views.index, name="user-management"),
    path("project-chart-values/", ProjectChartValuesAPIView.as_view(), name="project_chart_values"),
    path("deploy/<str:group_id>", views.deploy_view),
    path("register-user/<str:email>", views.register_user_view),
    path("list-users", UserManagementAPIView.as_view(), name="user_management_api"),
    path("list-groups", UserManagementAPIView.as_view(), name="user_management_api"),
    path("create-user", UserManagementAPIView.as_view(), name="user_management_api"),
    path("update-user", UserManagementAPIView.as_view(), name="user_management_api"),
    path("delete-user", UserManagementAPIView.as_view(), name="user_management_api"),
    path("create-group", UserManagementAPIView.as_view(), name="user_management_api"),
    path("delete-group", UserManagementAPIView.as_view(), name="user_management_api"),
    path("register-user-in-group/<str:email>", views.register_user_in_group_view),
    path("register-group/<str:group_id>", views.register_group_view),
    path("delete-group/<str:group_id>", views.delete_group_view),
    path("remove-user-from-group/<str:email>", views.remove_user_from_group_view),
]

# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.urls import path
from apps.user_management import views
from apps.user_management.views import (
    ProjectChartValuesAPIView,
    UserManagementAPIListUsersView,
    UserManagementAPIListGroupsView,
    UserManagementAPICreateUserView,
    UserManagementAPIUpdateUserView,
    UserManagementAPIDeleteUserView,
    UserManagementAPICreateGroupView,
    UserManagementAPIDeleteGroupView,
)

urlpatterns = [
    # The home page
    path("", views.index, name="user-management"),
    path("project-chart-values/", ProjectChartValuesAPIView.as_view(), name="project_chart_values"),
    path("deploy/<str:group_id>", views.deploy_view),
    path("register-user/<str:email>", views.register_user_view),
    path("list-users/", UserManagementAPIListUsersView.as_view(), name="list_users"),
    path("list-groups/", UserManagementAPIListGroupsView.as_view(), name="list_groups"),
    path("create-user/", UserManagementAPICreateUserView.as_view(), name="create_user"),
    path("update-user/", UserManagementAPIUpdateUserView.as_view(), name="update_user"),
    path("delete-user/", UserManagementAPIDeleteUserView.as_view(), name="delete_user"),
    path("create-group/", UserManagementAPICreateGroupView.as_view(), name="create_group"),
    path("delete-group/<str:group_id>", UserManagementAPIDeleteGroupView.as_view(), name="delete_group"),
    path("register-user-in-group/<str:email>", views.register_user_in_group_view),
    path("register-group/<str:group_id>", views.register_group_view),
    path("delete-group-view/<str:group_id>", views.delete_group_view),
    path("remove-user-from-group/<str:email>", views.remove_user_from_group_view),
]

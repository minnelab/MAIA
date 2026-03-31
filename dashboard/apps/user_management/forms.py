# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django import forms
from django.conf import settings
import datetime


class UserTableForm(forms.Form):

    def __init__(self, *args, **kwargs):
        if "users" in kwargs:
            super(UserTableForm, self).__init__()
        else:
            super(UserTableForm, self).__init__(*args, **kwargs)


        # maia_groups = get_groups_in_keycloak(settings= settings)
        # pending_projects = get_pending_projects(settings=settings, maia_project_model=MAIAProject)

        # for pending_project in pending_projects:
        #    maia_groups[pending_project] = pending_project + " (Pending)"

        # maia_groups = [(group, group) for group in maia_groups.values()]
        if "users" in kwargs:
            for i in kwargs["users"]:
                username = i["username"]
                # self.fields[f"namespace_{username}"] = forms.MultipleChoiceField(
                #    label='namespace',
                #    initial=i['namespace'].split(","),
                #    choices=maia_groups,
                # )
                self.fields[f"namespace_{username}"] = forms.CharField(max_length=150, label="namespace", initial=i["namespace"])
        else:
            for k in args[0]:
                if k.startswith("namespace"):
                    # self.fields[k] = forms.MultipleChoiceField(label='namespace', choices=maia_groups)
                    self.fields[k] = forms.CharField(max_length=150, label="namespace")

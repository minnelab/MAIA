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

        memory_limit = [(str(2**pow) + " Gi", str(2**pow) + " Gi") for pow in range(settings.MAX_MEMORY)]
        cpu_limit = [(str(2**pow), str(2**pow)) for pow in range(settings.MAX_CPU)]

        clusters = [(cluster, cluster) for cluster in settings.CLUSTER_NAMES.values()]
        clusters.append(("N/A", "N/A"))

        gpus = [(gpu["name"], gpu["name"]) for gpu in settings.GPU_SPECS]
        gpus.append(("N/A", "N/A"))

        minimal_envs = (("Base", "Base"), ("Pro", "Pro"))

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
                self.fields[f"namespace_{username}"] = forms.CharField(max_length=100, label="namespace", initial=i["namespace"])
        else:
            for k in args[0]:
                if k.startswith("namespace"):
                    # self.fields[k] = forms.MultipleChoiceField(label='namespace', choices=maia_groups)
                    self.fields[k] = forms.CharField(max_length=100, label="namespace")
                elif k.startswith("memory_limit"):

                    self.fields[k] = forms.ChoiceField(
                        label="memory_limit",
                        choices=memory_limit,
                    )
                elif k.startswith("cpu_limit"):

                    self.fields[k] = forms.ChoiceField(
                        label="cpu_limit",
                        choices=cpu_limit,
                    )
                elif k.startswith("date"):
                    self.fields[k] = forms.DateField(
                        label="date",
                        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
                        input_formats=["%Y-%m-%d"],
                    )
                elif k.startswith("conda"):
                    self.fields[k] = forms.FileField(label="conda")
                elif k.startswith("cluster"):
                    self.fields[k] = forms.ChoiceField(choices=clusters, label="cluster")
                elif k.startswith("gpu"):
                    self.fields[k] = forms.ChoiceField(choices=gpus, label="gpu")
                elif k.startswith("minimal_environment"):
                    self.fields[k] = forms.ChoiceField(label="minimal_environment", choices=minimal_envs)

        if "projects" in kwargs:
            for i in kwargs["projects"]:

                project_name = i

                self.fields[f"namespace_{project_name}"] = forms.CharField(max_length=100, label="namespace", initial=i)
                if kwargs["projects"][i]["memory_limit"] is None:
                    kwargs["projects"][i]["memory_limit"] = "2 Gi"
                if kwargs["projects"][i]["cpu_limit"] is None:
                    kwargs["projects"][i]["cpu_limit"] = "2"
                if kwargs["projects"][i]["date"] is None:
                    kwargs["projects"][i]["date"] = datetime.date.today
                if kwargs["projects"][i]["cluster"] is None:
                    kwargs["projects"][i]["cluster"] = "N/A"
                if kwargs["projects"][i]["gpu"] is None:
                    kwargs["projects"][i]["gpu"] = "N/A"
                if kwargs["projects"][i]["environment"] is None:
                    kwargs["projects"][i]["environment"] = "Base"
                self.fields[f"memory_limit_{project_name}"] = forms.ChoiceField(
                    label="memory_limit", choices=memory_limit, initial=kwargs["projects"][i]["memory_limit"]
                )
                self.fields[f"cpu_limit_{project_name}"] = forms.ChoiceField(
                    label="cpu_limit", choices=cpu_limit, initial=kwargs["projects"][i]["cpu_limit"]
                )
                self.fields[f"date_{project_name}"] = forms.DateField(
                    label="date",
                    initial=kwargs["projects"][i]["date"],
                    widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
                    input_formats=["%Y-%m-%d"],
                )

                self.fields[f"conda_{project_name}"] = forms.FileField(label="conda", initial=kwargs["projects"][i]["conda"])
                self.fields[f"cluster_{project_name}"] = forms.ChoiceField(
                    choices=clusters, label="cluster", initial=kwargs["projects"][i]["cluster"]
                )

                self.fields[f"gpu_{project_name}"] = forms.ChoiceField(
                    choices=gpus, label="gpu", initial=kwargs["projects"][i]["gpu"]
                )

                self.fields[f"minimal_environment_{project_name}"] = forms.ChoiceField(
                    label="minimal_environment", initial=kwargs["projects"][i]["environment"], choices=minimal_envs
                )

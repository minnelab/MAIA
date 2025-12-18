from django import forms


class ScaleDeployForm(forms.Form):
    scale_deploy = forms.IntegerField(label="Scale Deploy")


class DeleteJobForm(forms.Form):
    delete_job = forms.IntegerField(label="Delete Job")


class DeletePodForm(forms.Form):
    delete_pod = forms.IntegerField(label="Delete Pod")


class DeleteHelmChart(forms.Form):
    delete_helm_chart = forms.IntegerField(label="Delete Helm Chart")

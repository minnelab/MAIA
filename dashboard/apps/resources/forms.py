# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django import forms


class ResourceRequestForm(forms.Form):
    gpu_request = forms.IntegerField(min_value=0, max_value=4)
    cpu_request = forms.FloatField(min_value=0, max_value=20)
    memory_request = forms.FloatField(min_value=0, max_value=128)

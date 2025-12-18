# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.db import models


class MAIAInfo(models.Model):
    class Meta:
        app_label = "maia_info"

    email = models.CharField(
        max_length=255,
    )

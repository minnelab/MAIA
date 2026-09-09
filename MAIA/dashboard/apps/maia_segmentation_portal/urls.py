# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.urls import path
from apps.maia_segmentation_portal.views import ListSegmentationModelsAPIView

urlpatterns = [
    # The home page
    path("models/", ListSegmentationModelsAPIView.as_view(), name="segmentation_models_list"),
]

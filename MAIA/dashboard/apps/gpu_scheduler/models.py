from django.db import models


class GPUBooking(models.Model):
    class Meta:
        app_label = "gpu_scheduler"

    user_email = models.CharField(
        max_length=255,
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    gpu = models.CharField(max_length=255)
    namespace = models.CharField(max_length=255)

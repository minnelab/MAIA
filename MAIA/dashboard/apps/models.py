import datetime

from django.db import models
from rest_framework import serializers
import sys
import inspect
from django.contrib.auth.models import User

"""
Leave this Helper Class in the TOP of the file
"""


class Utils:
    @staticmethod
    def get_class(config, name: str) -> models.Model:
        return Utils.model_name_to_class(config[name])

    @staticmethod
    def get_manager(config, name: str) -> models.Manager:
        return Utils.get_class(config, name).objects

    @staticmethod
    def get_serializer(config, name: str):
        class Serializer(serializers.ModelSerializer):
            class Meta:
                model = Utils.get_class(config, name)
                fields = "__all__"

        return Serializer

    @staticmethod
    def model_name_to_class(name: str):
        all_classes = inspect.getmembers(sys.modules[__name__], inspect.isclass)
        for cls in all_classes:
            if cls[0] == name:
                return cls[1]
        # we are confident that never returns None
        return None


"""
Add your models below
"""


class Book(models.Model):
    class Meta:
        app_label = "dyn_datatables"

    name = models.CharField(max_length=100)


class MAIAProject(models.Model):

    class Meta:
        app_label = "authentication"

    id = models.AutoField(primary_key=True, null=False, auto_created=True)
    email = models.EmailField("email", max_length=150, null=True)
    namespace = models.CharField("namespace", max_length=150, blank=True, unique=True)
    gpu = models.CharField("gpu", max_length=150, blank=True, null=True)
    date = models.DateField("date", default=datetime.date.today)

    memory_limit = models.TextField("memory_limit", default="2G", null=True)
    cpu_limit = models.TextField("memory_limit", default="2", null=True)

    conda = models.TextField("conda", default="N/A", null=True)

    cluster = models.TextField("cluster", default="N/A", null=True)
    minimal_env = models.TextField("minimal_env", default="Base", null=True)
    description = models.TextField("description", blank=True, null=True)
    supervisor = models.EmailField("supervisor", max_length=150, null=True, blank=True)


class MAIAUser(User):
    class Meta:
        app_label = "authentication"

    namespace = models.CharField("namespace", max_length=150, blank=True)

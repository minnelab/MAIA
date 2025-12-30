# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
from django.test import TestCase
from apps.user_management.services import create_group, create_user
import datetime
from apps.models import MAIAProject, MAIAUser

class CreateGroupTests(TestCase):
    """Test the MAIAProject model with the new description and supervisor fields"""


    def setUp(self):
        self.admin_user = "admin@example.com"
        self.user = "user@example.com"
        self.supervisor = "supervisor@example.com"
        self.namespace = "test-project"
        self.gpu = "A100"
        self.date = datetime.date.today()
        self.memory_limit = "8 Gi"
        self.cpu_limit = "4"
        self.conda = "test-project_en.zip"
        self.cluster = "maia"
        self.minimal_env = "Base"
        self.project_description = "This is a test project for machine learning research"

    def test_create_group_with_supervisor(self):
        """Test creating a project with description and supervisor fields"""

        create_user(
            email=self.admin_user,
            username=self.admin_user,
            first_name="Admin",
            last_name="User",
            namespace=""
        )

        create_user(
            email=self.supervisor,
            username=self.supervisor,
            first_name="Supervisor",
            last_name="User",
            namespace=""
        )

        create_user(
            email=self.user,
            username=self.user,
            first_name="User",
            last_name="User",
            namespace=self.namespace
        )

        email_list = [self.admin_user, self.supervisor]
        create_group(
            group_id=self.namespace,
            gpu=self.gpu,
            date=self.date,
            memory_limit=self.memory_limit,
            cpu_limit=self.cpu_limit,
            conda=self.conda,
            cluster=self.cluster,
            minimal_env=self.minimal_env,
            user_email=self.admin_user,
            supervisor=self.supervisor,
            description=self.project_description,
            email_list=email_list
        )
        project = MAIAProject.objects.filter(namespace=self.namespace).first()

        self.assertEqual(project.namespace, self.namespace)
        self.assertEqual(project.gpu, self.gpu)
        self.assertEqual(project.date, self.date)
        self.assertEqual(project.memory_limit, self.memory_limit)
        self.assertEqual(project.cpu_limit, self.cpu_limit)
        self.assertEqual(project.conda, self.conda)
        self.assertEqual(project.cluster, self.cluster)
        self.assertEqual(project.email, self.supervisor)
        self.assertEqual(project.minimal_env, self.minimal_env)
        self.assertEqual(project.description, self.project_description)
        self.assertEqual(project.supervisor, self.supervisor)

        self.assertEqual(MAIAUser.objects.filter(email=self.admin_user).first().email, self.admin_user)
        self.assertEqual(MAIAUser.objects.filter(email=self.admin_user).first().namespace, self.namespace)

        self.assertEqual(MAIAUser.objects.filter(email=self.supervisor).first().email, self.supervisor)
        self.assertEqual(MAIAUser.objects.filter(email=self.supervisor).first().namespace, self.namespace)

        
        self.assertEqual(MAIAUser.objects.filter(email=self.user).first().email, self.user)
        #Expected to be empty because the user is not listed in the email_list, nor as project admin or supervisor
        self.assertEqual(MAIAUser.objects.filter(email=self.user).first().namespace, "")


    def test_create_group_with_nonexistent_supervisor(self):
        """Test creating a project with a supervisor email that does not exist as a user"""

        create_user(
            email=self.admin_user,
            username=self.admin_user,
            first_name="Admin",
            last_name="User",
            namespace=""
        )

        create_user(
            email=self.user,
            username=self.user,
            first_name="User",
            last_name="User",
            namespace=self.namespace
        )

        email_list = [self.admin_user]
        create_group(
            group_id=self.namespace,
            gpu=self.gpu,
            date=self.date,
            memory_limit=self.memory_limit,
            cpu_limit=self.cpu_limit,
            conda=self.conda,
            cluster=self.cluster,
            minimal_env=self.minimal_env,
            user_email=self.admin_user,
            email_list=email_list,
            description=self.project_description,
            supervisor=self.supervisor
        )

        project = MAIAProject.objects.filter(namespace=self.namespace).first()

        self.assertEqual(project.namespace, self.namespace)
        self.assertEqual(project.gpu, self.gpu)
        self.assertEqual(project.date, self.date)
        self.assertEqual(project.memory_limit, self.memory_limit)
        self.assertEqual(project.cpu_limit, self.cpu_limit)
        self.assertEqual(project.conda, self.conda)
        self.assertEqual(project.cluster, self.cluster)
        self.assertEqual(project.email, self.admin_user)
        self.assertEqual(project.minimal_env, self.minimal_env)
        self.assertEqual(project.description, self.project_description)
        self.assertEqual(project.supervisor, self.supervisor)

        self.assertEqual(MAIAUser.objects.filter(email=self.admin_user).first().email, self.admin_user)
        self.assertEqual(MAIAUser.objects.filter(email=self.admin_user).first().namespace, self.namespace)

        self.assertEqual(MAIAUser.objects.filter(email=self.user).first().email, self.user)
        self.assertEqual(MAIAUser.objects.filter(email=self.user).first().namespace, "")

        self.assertIsNone(MAIAUser.objects.filter(email=self.supervisor).first())

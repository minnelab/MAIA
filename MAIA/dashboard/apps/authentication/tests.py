# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.test import TestCase
from apps.models import MAIAProject, MAIAUser
from apps.authentication.forms import RegisterProjectForm
import datetime
from apps.authentication.views import register_project
from django.http import HttpRequest
from django.conf import settings


class MAIAProjectModelTests(TestCase):
    """Test the MAIAProject model with the new description and supervisor fields"""

    def test_create_project_with_description_and_supervisor(self):
        """Test creating a project with description and supervisor fields"""
        project = MAIAProject.objects.create(
            namespace='test-project',
            email='test@example.com',
            gpu='A100',
            date=datetime.date.today(),
            memory_limit='8G',
            cpu_limit='4',
            description='This is a test project for machine learning research',
            supervisor='supervisor@example.com'
        )

        self.assertEqual(project.namespace, 'test-project')
        self.assertEqual(project.description, 'This is a test project for machine learning research')
        self.assertEqual(project.supervisor, 'supervisor@example.com')

    def test_create_project_without_description_and_supervisor(self):
        """Test creating a project without description and supervisor (backward compatibility)"""
        project = MAIAProject.objects.create(
            namespace='test-project-2',
            email='test2@example.com',
            gpu='V100',
            date=datetime.date.today(),
            memory_limit='4G',
            cpu_limit='2'
        )

        self.assertEqual(project.namespace, 'test-project-2')
        self.assertIsNone(project.description)
        self.assertIsNone(project.supervisor)


class RegisterProjectFormTests(TestCase):
    """Test the RegisterProjectForm with the new fields"""

    def test_form_includes_description_and_supervisor(self):
        """Test that the form includes the description and supervisor fields"""
        form = RegisterProjectForm()

        self.assertIn('description', form.fields)
        self.assertIn('supervisor', form.fields)

    def test_description_and_supervisor_are_optional(self):
        """Test that description and supervisor fields are optional"""
        form = RegisterProjectForm()

        self.assertFalse(form.fields['description'].required)
        self.assertFalse(form.fields['supervisor'].required)


class RegisterProjectViewTests(TestCase):
    """Test the RegisterProjectView"""

    def setUp(self):
        self.user = MAIAUser.objects.create_user(
            email="test@example.com",
            username="test",
            first_name="Test",
            last_name="User",
            namespace=""
        )

        self.supervisor = MAIAUser.objects.create_user(
            email="supervisor@example.com",
            username="supervisor",
            first_name="Supervisor",
            last_name="User",
            namespace=""
        )
        self.non_existent_supervisor = "non-existent-supervisor@example.com"
        self.gpu = "NO"
        self.memory_limit = "8 Gi"
        self.cpu_limit = "4"
        self.namespace = "test-project"
        self.description = "This is a test project for machine learning research"
    
    def test_register_project_with_supervisor(self):
        """Test registering a project with a supervisor"""
        request = HttpRequest()
        request.method = "POST"
        request.data = {
            "namespace": self.namespace,
            "email": self.user.email,
            "gpu": self.gpu,
            "date": datetime.date.today(),
            "memory_limit": self.memory_limit,
            "cpu_limit": self.cpu_limit,
            "description": self.description,
            "supervisor": self.supervisor.email
        }
        response = register_project(request, api=True)
        self.assertEqual(response.data["msg"], "Request for Project Registration submitted successfully.")
        self.assertTrue(response.data["success"], True)

        self.assertEqual(MAIAProject.objects.filter(namespace=self.namespace).first().email, self.user.email)
        self.assertEqual(MAIAUser.objects.filter(email=self.user.email).first().namespace, self.namespace)
        self.assertEqual(MAIAUser.objects.filter(email=self.supervisor.email).first().namespace, self.namespace)

        self.assertEqual(MAIAProject.objects.filter(namespace=self.namespace).first().supervisor, self.supervisor.email)
        self.assertEqual(MAIAProject.objects.filter(namespace=self.namespace).first().description, self.description)


    def test_register_project_with_nonexistent_supervisor(self):
        """Test registering a project with a non-existent supervisor"""
        request = HttpRequest()
        request.method = "POST"
        request.data = {
            "namespace": self.namespace,
            "email": self.user.email,
            "gpu": self.gpu,
            "date": datetime.date.today(),
            "memory_limit": self.memory_limit,
            "cpu_limit": self.cpu_limit,
            "description": self.description,
            "supervisor": self.non_existent_supervisor
        }
        response = register_project(request, api=True)
        self.assertEqual(response.data["msg"], "Request for Project Registration submitted successfully.")
        self.assertTrue(response.data["success"], True)

        self.assertEqual(MAIAProject.objects.filter(namespace=self.namespace).first().email, self.user.email)
        self.assertEqual(MAIAUser.objects.filter(email=self.user.email).first().namespace, self.namespace)
        self.assertEqual(MAIAUser.objects.filter(email=self.non_existent_supervisor).first().namespace, f"{self.namespace},{settings.USERS_GROUP}")
        self.assertEqual(MAIAProject.objects.filter(namespace=self.namespace).first().description, self.description)
        self.assertEqual(MAIAProject.objects.filter(namespace=self.namespace).first().supervisor, self.non_existent_supervisor)

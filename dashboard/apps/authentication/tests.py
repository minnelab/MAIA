# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.test import TestCase
from apps.models import MAIAProject
from apps.authentication.forms import RegisterProjectForm
import datetime


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
            supervisor='Dr. Test Supervisor'
        )

        self.assertEqual(project.namespace, 'test-project')
        self.assertEqual(project.description, 'This is a test project for machine learning research')
        self.assertEqual(project.supervisor, 'Dr. Test Supervisor')

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

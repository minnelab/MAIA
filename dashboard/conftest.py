# project_root/conftest.py
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
os.environ.setdefault("DB_ENGINE", "sqlite")

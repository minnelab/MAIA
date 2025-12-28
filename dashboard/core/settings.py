# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os
import environ
import yaml

from MAIA.versions import define_maia_admin_versions

maia_dashboard_image_version = define_maia_admin_versions()["maia_dashboard_image_version"]

env = environ.Env(
    # set casting, default value
    DEBUG=(bool, True),
    SERVER=(str, ""),
    MINIO_URL=(str, ""),
    BUCKET_NAME=(str, ""),
)

DASHBOARD_VERSION = maia_dashboard_image_version
# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CORE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEBUG = env("DEBUG")
if DEBUG:
    MOUNT_DIR = BASE_DIR + "/config"
else:
    MOUNT_DIR = "/mnt/dashboard-config"
# Take environment variables from .env file
environ.Env.read_env(os.path.join(MOUNT_DIR, "env.env"))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY", default="S#perS3crEt_007")

# SECURITY WARNING: don't run with debug turned on in production!

MAX_MEMORY = env("MAX_MEMORY", default=7)
MAX_CPU = env("MAX_CPU", default=5)

MINIO_URL = env("MINIO_URL")
MINIO_PUBLIC_URL = env("MINIO_PUBLIC_URL", default=MINIO_URL)
MINIO_ACCESS_KEY = env("MINIO_ACCESS_KEY", default="N/A")
MINIO_SECRET_KEY = env("MINIO_SECRET_KEY", default="N/A")
MINIO_SECURE = env("MINIO_SECURE", default=True)
MINIO_PUBLIC_SECURE = env("MINIO_PUBLIC_SECURE", default=MINIO_SECURE)
BUCKET_NAME = env("BUCKET_NAME")

DISCORD_URL = env("DISCORD_URL", default=None)
DISCORD_SUPPORT_URL = env("DISCORD_SUPPORT_URL", default=None)


DEFAULT_INGRESS_HOST = env("DEFAULT_INGRESS_HOST", default="localhost")

OPENWEBAI_API_KEY = env("OPENWEBAI_API_KEY", default=None)
OPENWEBAI_URL = env("OPENWEBAI_URL", default=None)
ARGOCD_SERVER = env("ARGOCD_SERVER", default=None)
ARGOCD_CLUSTER = env("ARGOCD_CLUSTER", default=None)
# Assets Management
ASSETS_ROOT = os.getenv("ASSETS_ROOT", "/maia/static/assets")

HOSTNAME = env("SERVER", default="localhost")
# load production server from .env
ALLOWED_HOSTS = [
    "localhost",
    "localhost:85",
    "127.0.0.1",
    env("SERVER", default="http://127.0.0.1"),
    "http://dev." + env("SERVER", default="127.0.0.1"),
]
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:85",
    "http://127.0.0.1",
    "https://" + env("SERVER", default="http://127.0.0.1"),
    "http://dev." + env("SERVER", default="127.0.0.1"),
]

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps",
    "apps.authentication",
    "apps.home",  # Enable the inner home (home)
    "allauth",  # OAuth new
    "allauth.account",  # OAuth new
    "allauth.socialaccount",  # OAuth new
    "allauth.socialaccount.providers.github",  # OAuth new
    "sslserver",
    "rest_framework",
    "rest_framework.authtoken",
    "apps.dyn_datatables",
    "mozilla_django_oidc",  # Load after auth
    "bootstrap5",
    "apps.gpu_scheduler",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "mozilla_django_oidc.middleware.SessionRefresh",
]

ROOT_URLCONF = "core.urls"
LOGIN_REDIRECT_URL = "home"  # Route defined in home/urls.py
LOGOUT_REDIRECT_URL = "home"  # Route defined in home/urls.py
TEMPLATE_DIR = os.path.join(CORE_DIR, "apps/templates")  # ROOT dir for templates

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [TEMPLATE_DIR],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.context_processors.cfg_assets_root",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

LOCAL_DB_PATH = env("LOCAL_DB_PATH", default=BASE_DIR)
if os.environ.get("DB_ENGINE") and os.environ.get("DB_ENGINE") == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "appseed_db"),
            "USER": os.getenv("DB_USERNAME", "appseed_db_usr"),
            "PASSWORD": os.getenv("DB_PASS", "pass"),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", 3306),
        },
    }
else:
    print("INFO: Using local sqlite database at " + str(os.path.join(LOCAL_DB_PATH, "db.sqlite3")))
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(os.path.join(LOCAL_DB_PATH, "db.sqlite3")),
        }
    }

# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True

#############################################################
# SRC: https://devcenter.heroku.com/articles/django-assets

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/
STATIC_ROOT = os.path.join(CORE_DIR, "staticfiles")
STATIC_URL = "/maia/static/"

# Extra places for collectstatic to find static files.
STATICFILES_DIRS = (
    os.path.join(CORE_DIR, "apps/maia/static"),
    os.path.join(BASE_DIR, "apps/dyn_datatables/templates/static"),
)

# This is used by the API Generator
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

#############################################################
# OAuth settings

GITHUB_ID = os.getenv("GITHUB_ID", None)
GITHUB_SECRET = os.getenv("GITHUB_SECRET", None)
GITHUB_AUTH = GITHUB_SECRET is not None and GITHUB_ID is not None

OIDC_RP_CLIENT_ID = os.getenv("OIDC_RP_CLIENT_ID", None)
OIDC_RP_CLIENT_SECRET = os.getenv("OIDC_RP_CLIENT_SECRET", None)
OIDC_USERNAME = os.getenv("OIDC_USERNAME", None)
OIDC_ISSUER_URL = os.getenv("OIDC_ISSUER_URL", None)
OIDC_SERVER_URL = os.getenv("OIDC_SERVER_URL", None)
OIDC_REALM_NAME = os.getenv("OIDC_REALM_NAME", None)
OIDC_VERIFY_SSL = False
OIDC_OP_AUTHORIZATION_ENDPOINT = os.getenv("OIDC_OP_AUTHORIZATION_ENDPOINT", None)
OIDC_OP_TOKEN_ENDPOINT = os.getenv("OIDC_OP_TOKEN_ENDPOINT", None)
OIDC_OP_USER_ENDPOINT = os.getenv("OIDC_OP_USER_ENDPOINT", None)
OIDC_OP_JWKS_ENDPOINT = os.getenv("OIDC_OP_JWKS_ENDPOINT", None)
OIDC_RP_SIGN_ALGO = os.getenv("OIDC_RP_SIGN_ALGO", None)
OIDC_RP_SCOPES = os.getenv("OIDC_RP_SCOPES", None)
OIDC_CA_BUNDLE = os.getenv("OIDC_CA_BUNDLE", True)
ADMIN_GROUP = os.getenv("ADMIN_GROUP", "admin")
USERS_GROUP = os.getenv("USERS_GROUP", "users")
JWKS_TIMEOUT = int(os.getenv("JWKS_TIMEOUT", 10))
OIDC_STORE_ID_TOKEN = True

AUTHENTICATION_BACKENDS = (
    "core.MAIA_UA.HoneyCombOIDCAB",
    "core.custom-auth-backend.CustomBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)

SITE_ID = 1
ACCOUNT_EMAIL_VERIFICATION = "none"

SOCIALACCOUNT_PROVIDERS = {}

if GITHUB_AUTH:
    SOCIALACCOUNT_PROVIDERS["github"] = {"APP": {"client_id": GITHUB_ID, "secret": GITHUB_SECRET, "key": ""}}

#############################################################
# API Generator

API_GENERATOR = {
    # Register models below
    "books": "Book",
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.BasicAuthentication",
        "core.keycloak_auth.KeycloakAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "post_anon": "20/hour",
        "post_user": "200/hour",
    },
}
#############################################################
# DYNAMIC DATA Tables

DYNAMIC_DATATB = {
    "endpoint": "Model",  # don't change this line
    # Register models below
    "books": "Book",
}

CLUSTER_LINKS = {}
CLUSTER_NAMES = {}
PRIVATE_CLUSTERS = {}
API_URL = []
GPU_LIST = ["NO"]

GPU_SPECS = [{"name": "NO"}]


for root, dirs, files in os.walk(MOUNT_DIR):
    for file in files:
        if file.endswith(".yaml") or file.endswith(".yml"):
            with open(os.path.join(root, file)) as v_file:
                v_file = yaml.safe_load(v_file)

                if "maia_dashboard" in v_file and v_file["maia_dashboard"]["enabled"]:
                    if "services" in v_file:
                        CLUSTER_LINKS[v_file["cluster_name"]] = v_file["services"]
                    else:
                        CLUSTER_LINKS[v_file["cluster_name"]] = {}

                    if "api" in v_file:
                        CLUSTER_NAMES[v_file["api"]] = v_file["cluster_name"]
                        if v_file["api"] not in API_URL:
                            API_URL.append(v_file["api"])
                    else:
                        CLUSTER_NAMES[v_file["cluster_name"] + "-None"] = v_file["cluster_name"]
                        API_URL.append(v_file["cluster_name"] + "-None")

                    if v_file["maia_dashboard"]["token"] != "":
                        PRIVATE_CLUSTERS[v_file["api"]] = v_file["maia_dashboard"]["token"]
        if file.endswith(".yaml"):
            with open(os.path.join(root, file)) as v_file:
                v_file = yaml.safe_load(v_file)
                if "gpu_specs" in v_file:
                    for gpu in v_file["gpu_specs"]:
                        if gpu not in GPU_SPECS:
                            GPU_SPECS.append(gpu)

if "GLOBAL_NAMESPACES" in os.environ:
    GLOBAL_NAMESPACES = os.getenv("GLOBAL_NAMESPACES").split(",")
else:
    GLOBAL_NAMESPACES = []

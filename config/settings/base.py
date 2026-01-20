# backend/config/settings/base.py
from pathlib import Path
import os
from dotenv import load_dotenv
from datetime import timedelta


BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-dev-key")
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "django_filters",

    # Domain apps (modular monolith)
    "hm_core.common.apps.CommonConfig",
    "hm_core.tenants",
    "hm_core.facilities",
    "hm_core.iam.apps.IamConfig",
    "hm_core.patients",
    "hm_core.encounters.apps.EncountersConfig",
    "hm_core.tasks.apps.TasksConfig",
    "hm_core.clinical_docs.apps.ClinicalDocsConfig",
    "hm_core.rules",
    "hm_core.orders.apps.OrdersConfig",
    "hm_core.lab.apps.LabConfig",
    "hm_core.billing.apps.BillingConfig",
    "hm_core.audit",
    "hm_core.alerts.apps.AlertsConfig",
    "hm_core.charges.apps.ChargesConfig",
]

MIDDLEWARE = [
    # ✅ Put scope enforcement AFTER AuthenticationMiddleware
    # so request.user is available, but BEFORE views run.
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",

    # ✅ Enable this
    "hm_core.common.middleware.TenantFacilityScopeMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "hm"),
        "USER": os.getenv("DB_USER", "hm"),
        "PASSWORD": os.getenv("DB_PASSWORD", "hm"),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "hm_core.iam.auth.CookieOrHeaderJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_SCHEMA_CLASS": "hm_core.common.openapi.HMSAutoSchema",

    # ✅ Step 3.1: Standard error envelope
    "EXCEPTION_HANDLER": "hm_core.common.api.exceptions.api_exception_handler",

    # ✅ Step 3.2/3.3: Filtering + ordering + search support everywhere
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],

    # ✅ Step 3.2: Default pagination
    "DEFAULT_PAGINATION_CLASS": "hm_core.common.api.pagination.DefaultPagination",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "HM Software API",
    "DESCRIPTION": "Phase 0 (OPD) + Phase 1 (Lab) modular monolith backend",
    "VERSION": "0.1.0",

    # Better structure & compatibility
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": True,
    "SORT_OPERATION_PARAMETERS": True,

    # Show the auth scheme declared by your OpenApiAuthenticationExtension
    # (CookieOrHeaderJWTAuthenticationScheme in hm_core/iam/openapi.py)
    "SECURITY": [
        {"BearerOrCookieJWT": []}
    ],

    # Remove legacy /api/* endpoints, keep /api/v1/*
    "PREPROCESSING_HOOKS": [
        "hm_core.common.spectacular_hooks.preprocess_exclude_legacy_api",
    ],

    # Rename the ambiguous generated enum component deterministically
    "POSTPROCESSING_HOOKS": [
        "hm_core.common.spectacular_postprocess.rename_status249enum_to_tenant_status_enum",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=10),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,

    # Cookie settings
    "AUTH_COOKIE": "hm_access",
    "AUTH_COOKIE_REFRESH": "hm_refresh",
    "AUTH_COOKIE_SECURE": False,   # set True in production (HTTPS)
    "AUTH_COOKIE_HTTP_ONLY": True,
    "AUTH_COOKIE_SAMESITE": "Lax",
}

# CORS settings
# Development
CORS_ALLOW_ALL_ORIGINS = True  # Only for development!
CORS_ALLOW_CREDENTIALS = True

COMMON_IDEMPOTENCY_USE_DB = True

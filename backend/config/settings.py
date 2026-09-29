"""
Django settings for config project.
"""

import os
from corsheaders.defaults import default_headers
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path):
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file(BASE_DIR / ".env")
_load_env_file(BASE_DIR.parent / ".env")


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


SECRET_KEY = env("DJANGO_SECRET_KEY", "django-insecure-%vl+h0lcphru84t68rf+n9k829bxqa&i0sg(4!6tv^dkh#_!(+")
DEBUG = env("DJANGO_DEBUG", "true").lower() in ("1", "true", "yes", "on")
ALLOWED_HOSTS = [
    host.strip()
    for host in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "organizations.apps.OrganizationsConfig",
    "employees.apps.EmployeesConfig",
    "attendance.apps.AttendanceConfig",
    "dashboard",
    "authentication",
    "billing",
    "recognition.apps.RecognitionConfig",
    "payroll.apps.PayrollConfig",
    "exits.apps.ExitsConfig",
    "approvals.apps.ApprovalsConfig",
    "visitors.apps.VisitorsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "AIAttendance"),
        "USER": env("POSTGRES_USER", "postgres"),
        "PASSWORD": env("POSTGRES_PASSWORD", "123456"),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("DJANGO_TIME_ZONE", "Asia/Karachi")
USE_I18N = True
USE_TZ = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "organizations.authentication.TenantJWTAuthentication",
        "organizations.authentication.OrganizationApiKeyAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "organizations.permissions.HasOrganization",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in env(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:8000,http://localhost:8000",
    ).split(",")
    if origin.strip()
]
CORS_ALLOW_HEADERS = [*default_headers, "x-api-key"]

ATTENDANCE_MIN_ENROLLMENT_IMAGES = 5
CCTV_AUTOSTART = env("CCTV_AUTOSTART", "true").lower() in ("1", "true", "yes", "on")
ALERT_SCHEDULER = env("ALERT_SCHEDULER", "true").lower() in ("1", "true", "yes", "on")
ALERT_INTERVAL_SEC = int(env("ALERT_INTERVAL_SEC", "300") or "300")
TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = env("TWILIO_FROM_NUMBER", "")
TWILIO_WHATSAPP_FROM = env("TWILIO_WHATSAPP_FROM", "")

FRONTEND_URL = env("FRONTEND_URL", "http://localhost:5173")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_STARTER = env("STRIPE_PRICE_STARTER", "")
STRIPE_PRICE_PRO = env("STRIPE_PRICE_PRO", "")
SUPERADMIN_EMAIL = env("SUPERADMIN_EMAIL", "admin@aiattendance.local")
SUPERADMIN_PASSWORD = env("SUPERADMIN_PASSWORD", "Admin@12345")

EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "noreply@aiattendance.local")

STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

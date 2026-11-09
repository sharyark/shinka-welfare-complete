"""
Settings shared by every environment.

dev.py, test.py and prod.py import everything from here and change only what
differs. Secrets and anything that changes per server come from environment
variables (read from a .env file in development), never from Git.
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-insecure-key-never-use-in-production-0123456789")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# --- Applications -----------------------------------------------------------

DJANGO_APPS = [
    "unfold",  # must come before django.contrib.admin
    "unfold.contrib.filters",
    "unfold.contrib.simple_history",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    "simple_history",  # keeps every change to chosen models (e.g. need-score weights)
]

# Our own modules. New ones are added here phase by phase (see docs/architecture.md).
LOCAL_APPS = [
    "apps.core",
    "apps.societies",
    "apps.accounts",
    "apps.finance",
    "apps.registry",
    "apps.assessment",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.CurrentSocietyMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",  # history records who made each change
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

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

# --- Database ---------------------------------------------------------------
# DATABASE_URL example: postgres://shinka:shinka@localhost:5432/shinka
# Without it (missing or empty), a local SQLite file is used so the project runs with zero setup.
DATABASE_URL = env("DATABASE_URL", default="") or f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
DATABASES = {"default": env.db_url_config(DATABASE_URL)}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Auth -------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.PhoneBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Personal data protection ----------------------------------------------
# CNIC numbers are stored encrypted (Fernet) plus a keyed hash for finding duplicates.
# Generate a key:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Several comma-separated keys allow rotation: the first one encrypts, all of them decrypt.
# The defaults below are public, so they are for development and tests only (prod.py requires real ones).
FIELD_ENCRYPTION_KEYS = env.list(
    "FIELD_ENCRYPTION_KEYS", default=["loAyO8IVFQJtOcw6KHTdMfPELMHT-ajvmi4u0BNHT1w="]
)
# A secret mixed into CNIC hashes, so a leaked database can't be matched against a list of CNICs.
# Never change it once data exists: every stored hash would stop matching.
CNIC_HASH_PEPPER = env("CNIC_HASH_PEPPER", default="dev-only-pepper")

# --- Language & time --------------------------------------------------------

LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("ur", "اردو")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Karachi"
USE_I18N = True
USE_TZ = True

# --- Static & media files ---------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Django REST Framework --------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Secure by default: every endpoint needs login unless it opts out.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_RATES": {"anon": "60/min", "user": "300/min", "login": "10/min"},
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Shinka Welfare Management System API",
    "DESCRIPTION": "Central API for the admin panel, mobile app and public website.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    # Several models have a "status" field with different choices; give each its own name in the docs.
    "ENUM_NAME_OVERRIDES": {
        "DonationStatusEnum": "apps.finance.models.Donation.Status",
        "ExpenseStatusEnum": "apps.finance.models.Expense.Status",
        "HouseholdStatusEnum": "apps.registry.models.Household.Status",
        "AssessmentStatusEnum": "apps.assessment.models.Assessment.Status",
    },
}

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

# --- Celery (background jobs) -----------------------------------------------

CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = None
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_BEAT_SCHEDULE = {}  # periodic jobs are added by later phases

# --- Admin panel (Unfold) ---------------------------------------------------

UNFOLD = {
    "SITE_TITLE": "Shinka Welfare",
    "SITE_HEADER": "Shinka Welfare Society",
    "SITE_SYMBOL": "volunteer_activism",
    "SHOW_HISTORY": True,
    "COLORS": {
        "primary": {
            "50": "236 253 245",
            "100": "209 250 229",
            "200": "167 243 208",
            "300": "110 231 183",
            "400": "52 211 153",
            "500": "16 185 129",
            "600": "5 150 105",
            "700": "4 120 87",
            "800": "6 95 70",
            "900": "6 78 59",
            "950": "2 44 34",
        },
    },
}

# --- Logging ----------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}

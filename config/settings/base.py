"""Base settings shared by all environments."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-only-insecure-change-me",
)

DEBUG = False

ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.leagues",
    "apps.matches",
    "apps.predictions",
    "apps.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
        "BACKEND": ("django.template.backends.django.DjangoTemplates"),
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                ("django.template.context_processors.request"),
                ("django.contrib.auth.context_processors.auth"),
                ("django.contrib.messages.context_processors.messages"),
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    },
}

_AUTH_PREFIX = "django.contrib.auth.password_validation."

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (f"{_AUTH_PREFIX}UserAttributeSimilarityValidator"),
    },
    {
        "NAME": (f"{_AUTH_PREFIX}MinimumLengthValidator"),
    },
    {
        "NAME": (f"{_AUTH_PREFIX}CommonPasswordValidator"),
    },
    {
        "NAME": (f"{_AUTH_PREFIX}NumericPasswordValidator"),
    },
]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Europe/Moscow"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {
        "BACKEND": ("django.core.files.storage.FileSystemStorage"),
    },
    "staticfiles": {
        "BACKEND": ("whitenoise.storage.CompressedManifestStaticFilesStorage"),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# OverPick / API-Football
API_FOOTBALL_KEY = os.environ.get(
    "API_FOOTBALL_KEY",
    "",
)
API_FOOTBALL_BASE_URL = os.environ.get(
    "API_FOOTBALL_BASE_URL",
    "https://v3.football.api-sports.io",
)
API_FOOTBALL_MIN_INTERVAL = float(
    os.environ.get("API_FOOTBALL_MIN_INTERVAL", "0.5"),
)

MODEL_N = int(os.environ.get("MODEL_N", "5"))
MODEL_MIN_N = int(os.environ.get("MODEL_MIN_N", "3"))
MODEL_SHRINK_K = float(os.environ.get("MODEL_SHRINK_K", "3"))
MODEL_LAST_WEIGHT = float(
    os.environ.get("MODEL_LAST_WEIGHT", "0.6"),
)

# Default horizon for build_predictions / Upcoming UI.
PREDICTION_HORIZON_DAYS = int(
    os.environ.get("PREDICTION_HORIZON_DAYS", "3"),
)

SIGNAL_THRESHOLD_O15 = float(
    os.environ.get("SIGNAL_THRESHOLD_O15", "0.82"),
)
SIGNAL_THRESHOLD_O25 = float(
    os.environ.get("SIGNAL_THRESHOLD_O25", "0.60"),
)
SIGNAL_THRESHOLD_O35 = float(
    os.environ.get("SIGNAL_THRESHOLD_O35", "0.42"),
)

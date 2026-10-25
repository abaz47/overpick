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
# Half-life (days) for last-N venue form decay.
MODEL_DECAY_HALFLIFE_DAYS = float(
    os.environ.get("MODEL_DECAY_HALFLIFE_DAYS", "90"),
)
# Dixon–Coles ρ (negative → more low-score dependence).
MODEL_DC_RHO = float(os.environ.get("MODEL_DC_RHO", "-0.1"))
# Caps to keep λ realistic (anti blow-up).
MODEL_INDEX_MIN = float(os.environ.get("MODEL_INDEX_MIN", "0.6"))
MODEL_INDEX_MAX = float(os.environ.get("MODEL_INDEX_MAX", "1.5"))
MODEL_LAMBDA_SIDE_MAX = float(
    os.environ.get("MODEL_LAMBDA_SIDE_MAX", "2.8"),
)
MODEL_LAMBDA_TOTAL_MAX = float(
    os.environ.get("MODEL_LAMBDA_TOTAL_MAX", "5.0"),
)

# Default horizon for build_predictions / Upcoming UI.
PREDICTION_HORIZON_DAYS = int(
    os.environ.get("PREDICTION_HORIZON_DAYS", "3"),
)

# Single Pick tier (former Strong levels).
SIGNAL_THRESHOLD_O15 = float(
    os.environ.get("SIGNAL_THRESHOLD_O15", "0.88"),
)
SIGNAL_THRESHOLD_O25 = float(
    os.environ.get("SIGNAL_THRESHOLD_O25", "0.65"),
)
SIGNAL_THRESHOLD_O35 = float(
    os.environ.get("SIGNAL_THRESHOLD_O35", "0.55"),
)
# Do not tip O3.5 above this (overconfidence guard).
SIGNAL_O35_MAX_PROB = float(
    os.environ.get("SIGNAL_O35_MAX_PROB", "0.70"),
)

# Soft launch (Today's picks + KPI). Format: MSK naive ISO.
SITE_LAUNCH_AT = os.environ.get(
    "SITE_LAUNCH_AT",
    "2026-10-24T18:00:00",
)
# History storage / won-picked from this MSK datetime.
STATS_SINCE = os.environ.get(
    "STATS_SINCE",
    "2026-10-26T00:00:00",
)

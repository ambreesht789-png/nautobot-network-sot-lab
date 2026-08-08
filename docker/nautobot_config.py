"""Nautobot configuration for the Network Source of Truth Lab.

This configuration is intended for local demonstration environments. It reads
all sensitive values from environment variables so that no credentials are
committed to version control.
"""

import os

from nautobot.core.settings import *
from nautobot.core.settings_funcs import is_truthy

# ---------------------------------------------------------------------------
# Core settings
# ---------------------------------------------------------------------------

ALLOWED_HOSTS = os.getenv("NAUTOBOT_ALLOWED_HOSTS", "*").split(" ")
SECRET_KEY = os.getenv("NAUTOBOT_SECRET_KEY", "")
DEBUG = is_truthy(os.getenv("NAUTOBOT_DEBUG", "False"))

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "NAME": os.getenv("NAUTOBOT_DB_NAME", "nautobot"),
        "USER": os.getenv("NAUTOBOT_DB_USER", "nautobot"),
        "PASSWORD": os.getenv("NAUTOBOT_DB_PASSWORD", ""),
        "HOST": os.getenv("NAUTOBOT_DB_HOST", "postgres"),
        "PORT": os.getenv("NAUTOBOT_DB_PORT", "5432"),
        "CONN_MAX_AGE": int(os.getenv("NAUTOBOT_DB_TIMEOUT", "300")),
        "ENGINE": "django.db.backends.postgresql",
    }
}

# ---------------------------------------------------------------------------
# Redis / Celery
# ---------------------------------------------------------------------------

REDIS_HOST = os.getenv("NAUTOBOT_REDIS_HOST", "redis")
REDIS_PORT = os.getenv("NAUTOBOT_REDIS_PORT", "6379")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# ---------------------------------------------------------------------------
# Installed apps
# ---------------------------------------------------------------------------

PLUGINS = [
    "nautobot_golden_config",
]

PLUGINS_CONFIG = {
    "nautobot_golden_config": {
        "enable_backup": True,
        "enable_compliance": True,
        "enable_intended": True,
        "enable_sotagg": True,
        "enable_plan": False,
        "enable_deploy": False,
    },
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL = "DEBUG" if DEBUG else "INFO"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "loggers": {
        "nautobot": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
        },
    },
}

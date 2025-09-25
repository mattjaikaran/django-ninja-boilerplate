"""Django settings for api project - Common settings.

This module contains settings that are common across all environments.
Environment-specific settings should be defined in dev.py or prod.py.
"""

import os
from datetime import timedelta
from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# for environment variable using django-environ library
# this allows you to use the .env file to set the environment variables
# throughout the entire application
env = environ.Env(
    # Set casting and default values
    DEBUG=(bool, False),
    SECRET_KEY=(str, ""),
    ALLOWED_HOSTS=(list, []),
    DB_NAME=(str, ""),
    DB_USER=(str, ""),
    DB_PASSWORD=(str, ""),
    DB_HOST=(str, ""),
    DB_PORT=(str, ""),
    DB_URL=(str, ""),
)

# Read .env file
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")

FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")

# Application definition
INSTALLED_APPS = [
    #####
    # Django Unfold admin panel
    #####
    "unfold",  # django-unfold
    "unfold.contrib.filters",  # django-unfold-filters
    "unfold.contrib.forms",  # django-unfold-forms
    "unfold.contrib.inlines",
    "unfold.contrib.import_export",
    #####
    # Django core packages
    #####
    "django.contrib.admin",  # admin
    "django.contrib.auth",  # auth
    "django.contrib.contenttypes",  # content types
    "django.contrib.sessions",  # sessions
    "django.contrib.messages",  # messages
    "django.contrib.staticfiles",  # static files
    #####
    # django-ninja-extra libraries
    #####
    "ninja_extra",  # django-ninja-extra
    "ninja_jwt",  # django-ninja-jwt
    #####
    # user created apps
    #####
    "core",  # core app
    "todos",  # todos app
    #####
    # third party packages
    #####
    "corsheaders",  # django-cors-headers for cross-origin requests
    "import_export",  # django-import-export for importing and exporting data
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",  # security middleware
    "django.contrib.sessions.middleware.SessionMiddleware",  # session middleware
    "corsheaders.middleware.CorsMiddleware",  # django-cors-headers
    "django.middleware.common.CommonMiddleware",  # common middleware
    "django.middleware.csrf.CsrfViewMiddleware",  # csrf view middleware
    "django.contrib.auth.middleware.AuthenticationMiddleware",  # authentication middleware
    "django.contrib.messages.middleware.MessageMiddleware",  # message middleware
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "api.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",  # django templates
        "DIRS": [],  # directories
        "APP_DIRS": True,  # app directories
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",  # debug context processor
                "django.template.context_processors.request",  # request context processor
                "django.contrib.auth.context_processors.auth",  # auth context processor
                "django.contrib.messages.context_processors.messages",  # messages context processor
            ],
        },
    },
]

WSGI_APPLICATION = "api.wsgi.application"  # wsgi application

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",  # postgresql database
        "NAME": env("DB_NAME"),  # database name
        "USER": env("DB_USER"),  # database user
        "PASSWORD": env("DB_PASSWORD"),  # database password
        "HOST": env("DB_HOST"),  # database host
        "PORT": env("DB_PORT"),  # database port
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators
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

# Custom user model
AUTH_USER_MODEL = "core.User"

# Django Ninja JWT settings
NINJA_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("ninja_jwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
    "TOKEN_USER_CLASS": "core.User",
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
}

# Django Ninja Extra settings
NINJA_EXTRA = {
    "PAGINATION_CLASS": "ninja_extra.pagination.PageNumberPaginationExtra",  # included pagination
    "PAGINATION_PER_PAGE": 50,  # 50 items per page
    "INJECTOR_MODULES": [],  # injector modules
    "THROTTLE_CLASSES": [
        "ninja_extra.throttling.AnonRateThrottle",  # anonymous user throttling
        "ninja_extra.throttling.UserRateThrottle",  # authenticated user throttling
    ],
    "THROTTLE_RATES": {
        "user": "1000/day",  # 1000 requests per day for authenticated users
        "anon": "100/day",  # 100 requests per day for anonymous users
    },
    "NUM_PROXIES": None,  # number of proxies
    "ORDERING_CLASS": "ninja_extra.ordering.Ordering",  # included ordering
    "SEARCHING_CLASS": "ninja_extra.searching.Search",  # included searching
}

# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/
LANGUAGE_CODE = "en-us"  # language code
TIME_ZONE = "UTC"  # time zone
USE_I18N = True  # use i18n
USE_TZ = True  # use tz

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/
STATIC_URL = "static/"
STATIC_ROOT = "static/"

# Media files
# MEDIA_URL = "media/"
# MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "django.db.backends": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "import_export": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "core": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "core.schemas": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "core.controllers": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "todos": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

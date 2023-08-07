"""
Django settings for door_commander project.

Generated by 'django-admin startproject' using Django 3.1.7.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""
import ipaddress
import json
import logging
import logging.config
import os
import pickle
import socket
from pathlib import Path

from celery.schedules import crontab
from ipware.descriptor import ReverseProxy, Header

import door_commander.tasks

# TODO this file becomes too long, use dynaconf or similar and split it up.

from django.core.management.utils import get_random_secret_key
from icecream import ic

from .atomic_globals import AtomicGlobals

# This tool allows to either declare all or no settings at all for a specific feature.
from .loglevel import AUDIT

atomic_globals = AtomicGlobals()

# ================================================================
# Logging
# ================================================================
# optionally install `rich` for colored logging

log = logging.getLogger(__name__)

try:
    from rich.logging import RichHandler
except:
    RichHandler = None


logging.addLevelName(AUDIT, "AUDIT")
_DJANGO_LOGGING = os.getenv("DJANGO_LOGGING")
LOGGING = json.loads(_DJANGO_LOGGING) if _DJANGO_LOGGING else {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(name)s %(process)d %(thread)d %(message)s',
        },
        'simple': {
            'format': '%(message)s',
        },
        'complex': {
            'format': '%(processName)s#%(process)d @ %(module)s:%(name)s:%(funcName)s: %(message)s',
        },
    },

    'handlers': {
        'console': {
            'class': 'rich.logging.RichHandler' if RichHandler else 'logging.StreamHandler',
            'formatter': 'simple' if RichHandler else 'verbose'
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'decorated_paho_mqtt.mqtt_framework': {
            'handlers': ['console'],
            # paho seems to log everything, including connection errors at level 16, which is between DEBUG and INFO
            'level': 'INFO',
            'propagate': False,
        }
    },
}
logging.config.dictConfig(LOGGING)

# ================================================================

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ================================================================
# Django Security Settings
# ================================================================

DEBUG_FILE = BASE_DIR.joinpath("./data/ACTIVATE_DEBUG_MODE")
# If you want to debug; create a file in the directory indicated above.
DEBUG = DEBUG_FILE.exists()

# this allows to use {% if debug %} in django templates.
INTERNAL_IPS = ['127.0.0.1', '::1']

SECRET_KEY_FILE = BASE_DIR.joinpath("./data/django-secret-key.json")

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

def load_or_create_secret_key() -> str:
    # TODO we now pass all secrets via environment, we might want to do this here too.
    if SECRET_KEY_FILE.exists():
        secret = json.load(open(SECRET_KEY_FILE, "r"))
        return secret
    else:
        secret = get_random_secret_key()
        json.dump(secret, open(SECRET_KEY_FILE, "w"))
        return secret


SECRET_KEY = load_or_create_secret_key()

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '[::1]',
    'python',
    'sesam.zam.haus',
]

# ================================================================
# Framework applications
# ================================================================
# Our own apps are declared at the bottom of this file.


INSTALLED_APPS = [
    'django.contrib.admin',  # https://docs.djangoproject.com/en/3.2/ref/contrib/admin/
    'django.contrib.auth',  # https://docs.djangoproject.com/en/3.2/ref/contrib/auth/
    'django.contrib.contenttypes',  # https://docs.djangoproject.com/en/3.2/ref/contrib/contenttypes/
    'django.contrib.sessions',  # https://docs.djangoproject.com/en/3.2/topics/http/sessions/
    'django.contrib.messages',  # https://docs.djangoproject.com/en/3.2/ref/contrib/messages/
    'django.contrib.staticfiles',  # https://docs.djangoproject.com/en/3.2/ref/contrib/staticfiles/
]

MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
]


SILENCED_SYSTEM_CHECKS = [
    "security.W008", # SECURE_SSL_REDIRECT -> responsibility of nginx.
    "security.W004", # SECURE_HSTS_SECONDS -> responsibility of nginx.
]
SESSION_COOKIE_SECURE = False if DEBUG else True
CSRF_COOKIE_SECURE = False if DEBUG else True

if DEBUG:
    INSTALLED_APPS += [
        'django_extensions',
        #'debug_toolbar',
    ]
    MIDDLEWARE += [
        #'debug_toolbar.middleware.DebugToolbarMiddleware',
    ]

# ================================================================
# URLs
# ================================================================

ROOT_URLCONF = 'door_commander.urls'

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# ================================================================
# Jinja and Django Template Renderers and Paths
# ================================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.jinja2.Jinja2',
        'DIRS': ["jinja-templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'environment': 'web_homepage.jinja.environment'
        },
    },
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ["templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ================================================================
# Webserver
# ================================================================

WSGI_APPLICATION = 'door_commander.wsgi.application'

# ================================================================
# Authz Microservice
# ================================================================

OPA_BEARER_TOKEN = os.getenv("OPA_BEARER_TOKEN") or ""
OPA_URL = os.getenv("OPA_URL")

# ================================================================
# Database
# ================================================================


# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

POSTGRES_DB = os.getenv("POSTGRES_DB")
if not POSTGRES_DB:
    if DEBUG:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'data' / 'db.sqlite3',
            }
        }
else:
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_USER = os.getenv("POSTGRES_USER")
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': POSTGRES_DB,
            'USER': POSTGRES_USER,
            'PASSWORD': POSTGRES_PASSWORD,
            'HOST': 'db',
        }
    }

# ================================================================

# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# ================================================================

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_URL = '/static/'
# STATICFILES_DIRS = ["static"]
STATIC_ROOT = os.getenv("COLLECTSTATIC_DIR", None)

# ================================================================
# IP Filtering Configuration # TODO currently without effect
# ================================================================

# TODO might be a vuln in some networks
PROXY_HOSTNAME = "nginx"
try:
    _, _, _nginx_address = socket.gethostbyname_ex(PROXY_HOSTNAME)
except socket.gaierror:
    _nginx_address = None

if _nginx_address:
    IPWARE_REVERSE_PROXIES = [
        ReverseProxy(Header("X-Forwarded-For"), *_nginx_address),
    ]
else:
    IPWARE_REVERSE_PROXIES = []

PERMITTED_IP_NETWORKS = [ipaddress.ip_network('192.168.0.0/24')]
IPWARE_KWARGS = {}

# ================================================================
# MQTT Configuration
# ================================================================

# https://www.eclipse.org/paho/index.php?page=clients/python/docs/index.php#connect-reconnect-disconnect
# MQTT_CLIENT_KWARGS = dict(client_id="door_commander", transport="tcp")
MQTT_CLIENT_KWARGS = dict(transport="tcp")
MQTT_PASSWD_CONTROLLER = os.getenv("MQTT_PASSWD_CONTROLLER")
MQTT_SERVER_KWARGS = os.getenv("MQTT_CONNECTION")
if MQTT_SERVER_KWARGS is None:
    MQTT_SERVER_KWARGS = dict(host="127.0.0.1", port=1883, keepalive=10)
else:
    MQTT_SERVER_KWARGS = json.loads(MQTT_SERVER_KWARGS)
if MQTT_PASSWD_CONTROLLER:
    MQTT_PASSWORD_AUTH = dict(username="controller", password=MQTT_PASSWD_CONTROLLER)
else:
    MQTT_PASSWORD_AUTH = None  # dict(username=...,password=...)

MQTT_TLS = False

# ================================================================
# Authentication and OpenID Connect Configuration
# ================================================================

AUTH_USER_MODEL = "accounts.User"

# Add 'mozilla_django_oidc' authentication backend
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        # TODO we should use a german list for our target group, however, these are difficult to find.
        #  Use Duden, given names, surnames, sports clubs and qwertz-Keywalks?
        # https://docs.djangoproject.com/en/3.1/topics/auth/passwords/#password-validation
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
        # 'password_list_path' : '...'
        # This file should contain one lowercase password per line and may be plain text or gzipped.
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

with atomic_globals:
    # ic(dict(os.environ))
    OIDC_RP_CLIENT_ID = os.environ['OIDC_RP_CLIENT_ID']
    # TODO configuration option
    OIDC_OP_JWKS_ENDPOINT = "http://keycloak_bv.nginx_door_commander_external:8080/realms/ZAM/protocol/openid-connect/certs"

    OIDC_RP_CLIENT_SECRET = os.environ['OIDC_RP_CLIENT_SECRET']
    OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 60 * 15
    OIDC_OP_AUTHORIZATION_ENDPOINT = os.environ['OIDC_OP_AUTHORIZATION_ENDPOINT']
    OIDC_OP_TOKEN_ENDPOINT = os.environ['OIDC_OP_TOKEN_ENDPOINT']
    OIDC_OP_USER_ENDPOINT = os.environ['OIDC_OP_USER_ENDPOINT']
    OIDC_OP_LOGOUT_URL = os.environ['OIDC_OP_LOGOUT_URL']
    if OIDC_OP_LOGOUT_URL:
        OIDC_OP_LOGOUT_URL_METHOD = 'accounts.auth.provider_logout'
    # TODO configuration option
    OIDC_RP_SIGN_ALGO = "RS256"
if atomic_globals:
    OIDC = True
    INSTALLED_APPS += [
        'mozilla_django_oidc',  # Load after auth
    ]
    AUTHENTICATION_BACKENDS += [
        #    'mozilla_django_oidc.auth.OIDCAuthenticationBackend',
        'accounts.auth.CustomOidcAuthenticationBackend',
    ]
    MIDDLEWARE += [
        # this might make API requests a bit more difficult
        'mozilla_django_oidc.middleware.SessionRefresh',
    ]
    log.info("Successfully loaded OpenID Connect configuration")
else:
    OIDC = False
    log.warning("Did not load OpenID Connect configuration", exc_info=atomic_globals.exc_info)

# ================================================================
# GraphQL
# ================================================================

INSTALLED_APPS += [
    # 'django.contrib.staticfiles', # Required for GraphiQL
    'graphene_django',
]

# Check http://127.0.0.1:8000/graphql
# You could query:
"""{
  users {
    id
    fullName
    displayName
    username
    isSuperuser
    dateJoined
  }
  _debug{
    sql {
      sql
      transId
      transStatus
      isoLevel
      encoding
      vendor
      duration
      startTime
      stopTime
      isSlow
      isSelect
    }
  }
}
"""

GRAPHENE = {
    'SCHEMA': 'api.gql.schema',  # Where your Graphene schema lives
    'MIDDLEWARE': [
        'graphene_django.debug.DjangoDebugMiddleware',
        # this hides exception messages, except for explicit graphql exceptions:
        'api.gql.SecurityMiddleware',
    ] if DEBUG else [],
}

# ================================================================
# Celery
# ================================================================
CELERY_BROKER_URL = "redis://redis:6379"
CELERY_RESULT_BACKEND = "redis://redis:6379"

CELERY_BEAT_SCHEDULE = {
    # "debug_task": {"task": "door_commander.tasks.debug_task", "schedule": crontab(minute="*/1"), },
    "publish_door_names": {
        "task": "doors.tasks.publish_door_names",
        "schedule": crontab(minute="*/15"),
    },
}

# ================================================================
# Our own functional apps
# ================================================================

INSTALLED_APPS += [
    'doors',
    'accounts',
    'api',
    'web_homepage',
    'clientipaddress',
]

# ================================================================
# Mail
# ================================================================

# TODO
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

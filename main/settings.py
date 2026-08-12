"""
Django settings for VGSync backend.
Supports both local development and production deployment.
"""

from pathlib import Path
from datetime import timedelta
import os

# --------------------------------------------------
# Basic Paths
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# --------------------------------------------------
# Security
# --------------------------------------------------
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-dev-key-for-local')
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*,localhost,127.0.0.1,192.168.1.99').split(',')

# --------------------------------------------------
# Installed Apps
# --------------------------------------------------
INSTALLED_APPS = [
    # Django Core Apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    

    # 3rd Party Apps
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'django_filters',
    'corsheaders',

    # Local Apps
    'core.apps.CoreConfig',  
]

# Use custom User model
AUTH_USER_MODEL = 'core.User'

# --------------------------------------------------
# Middleware
# --------------------------------------------------
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # must be first
    'django.middleware.security.SecurityMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'main.urls'

# --------------------------------------------------
# Templates
# --------------------------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'main.wsgi.application'

# --------------------------------------------------
# Database
# --------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DJANGO_DB_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': os.environ.get('DJANGO_DB_NAME', BASE_DIR / 'db.sqlite3'),
        'USER': os.environ.get('DJANGO_DB_USER', ''),
        'PASSWORD': os.environ.get('DJANGO_DB_PASSWORD', ''),
        'HOST': os.environ.get('DJANGO_DB_HOST', ''),
        'PORT': os.environ.get('DJANGO_DB_PORT', ''),
    }
}

# --------------------------------------------------
# Password Validation
# --------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --------------------------------------------------
# Internationalization
# --------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kathmandu'
USE_I18N = True
USE_TZ = True

# --------------------------------------------------
# Static & Media
# --------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --------------------------------------------------
# Django REST Framework
# --------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
     'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DATETIME_FORMAT': "%Y-%m-%d %H:%M:%S",
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# --------------------------------------------------
# JWT
# --------------------------------------------------
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=int(os.environ.get('JWT_ACCESS_HOURS', 10))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.environ.get('JWT_REFRESH_DAYS', 7))),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# --------------------------------------------------
# CORS
# --------------------------------------------------
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = os.environ.get(
        'CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:8000'
    ).split(',')

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'origin',
    'dnt',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# --------------------------------------------------
# Logging
# --------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
}

# --------------------------------------------------
# Default Auto Field
# --------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --------------------------------------------------
# SAFE RESTORE MODE (IMPORTANT FOR loaddata)
# --------------------------------------------------
SKIP_SIGNALS = os.environ.get('SKIP_SIGNALS', 'False') == '1'
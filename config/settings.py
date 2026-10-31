"""Django settings for the LIP (Label Inspection Project).

Everything environment-specific is read from environment variables (see `.env.example`).
Sections: core, apps, database, auth (M1), REST framework, i18n, static/media,
email, logging, external services, test overrides.
"""

import os
import sys
from pathlib import Path

import django

BASE_DIR = Path(__file__).resolve().parent.parent

try:  # load local overrides from .env (real environment variables still take priority)
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / '.env')
except ImportError:  # python-dotenv not installed: rely on real environment variables
    pass


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, '1' if default else '0') == '1'


# --- Core ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-only-change-me')
DEBUG = env_bool('DJANGO_DEBUG', default=True)
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Applications (FDS section 8) ---------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'apps.accounts',  # M1 Authentication and Users
    'apps.catalogue',  # M2 Product Catalogue
    'apps.compliance',  # M4 Compliance Rules
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.accounts.context_processors.navigation',
            ],
        },
    },
]

# --- Database (PostgreSQL; SQLite only as a local shortcut) -------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'lip'),
        'USER': os.environ.get('DB_USER', 'lip'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}
if env_bool('USE_SQLITE'):
    DATABASES['default'] = {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}

# --- M1 Authentication & Users ------------------------------------------------------
AUTH_USER_MODEL = 'accounts.User'
AUTHENTICATION_BACKENDS = ['apps.accounts.backends.EmailOrUsernameBackend']
LOGIN_URL = '/login/'  # page route; the JSON login endpoint is /api/auth/login/
FRONTEND_RESET_URL = os.environ.get('FRONTEND_RESET_URL', 'http://localhost:8000/reset-password')

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

SESSION_COOKIE_AGE = 60 * 60 * 8  # one working shift
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG  # HTTPS-only cookies outside development (FDS 17)
CSRF_COOKIE_SECURE = not DEBUG

# --- Django REST framework ----------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_RATES': {
        'login': os.environ.get('THROTTLE_LOGIN', '10/min'),
        'password_reset': os.environ.get('THROTTLE_PASSWORD_RESET', '5/hour'),
        'product_lookup': os.environ.get('THROTTLE_PRODUCT_LOOKUP', '60/min'),
    },
}

# --- Internationalisation -----------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# --- Static and media files ---------------------------------------------------------
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'  # inspection images / evidence; serve via protected storage in production

# --- Email (password reset). Django 6.1 replaced EMAIL_BACKEND with MAILERS ----------
_EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
if django.VERSION >= (6, 1):
    MAILERS = {'default': {'BACKEND': _EMAIL_BACKEND}}
else:
    EMAIL_BACKEND = _EMAIL_BACKEND
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'no-reply@lip.local')

# --- Logging ------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {'lip': {'handlers': ['console'], 'level': 'INFO'}},
}

# --- External services (FDS section 5): keys come from the environment only --------
AI_API_KEY = os.environ.get('AI_API_KEY', '')
PRODUCT_API_BASE_URL = os.environ.get('PRODUCT_API_BASE_URL', 'https://world.openfoodfacts.org/api/v2')
PRODUCT_API_TIMEOUT = float(os.environ.get('PRODUCT_API_TIMEOUT', '5'))  # seconds; never block an inspection
PRODUCT_API_USER_AGENT = os.environ.get('PRODUCT_API_USER_AGENT', 'LabelInspect/1.0 (internal inspection tool)')

# --- Test overrides: fast hashing, never active outside `manage.py test` -----------
if 'test' in sys.argv:
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

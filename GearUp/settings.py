import os
from pathlib import Path
from decouple import config, Csv, Config, RepositoryEnv
import cloudinary


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY")

# DEBUG = config("DEBUG", default=False, cast=bool)
DEBUG = False

ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())

ENV_FILE = BASE_DIR.parent / ".env"
config = Config(RepositoryEnv(str(ENV_FILE)))

CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", cast=Csv()) 


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "django_otp",
    "django_otp.plugins.otp_email",
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'django.contrib.humanize',
    'home',
    'register',
    'user_account',
    'widget_tweaks',
    'products',
    'address',
    'wishlist',
    'cart',
    'orders',
    'coupons',
    'offers',
    'transaction',
    'wallet.apps.WalletConfig',
    'cloudinary',
    'cloudinary_storage',
]

cloudinary.config(
    cloud_name = config("CLOUD_NAME"),
    api_key = config("API_KEY"),
    api_secret = config("API_SECRET"),
)

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

RAZORPAY_KEY_ID = config("RAZORPAY_KEY_ID") 
RAZORPAY_KEY_SECRET = config("RAZORPAY_KEY_SECRET")

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "django_otp.middleware.OTPMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

ROOT_URLCONF = 'GearUp.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ["templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'GearUp.wsgi.application'


# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql_psycopg2',
#         'NAME': config("NAME"),
#         'USER': 'postgres',
#         'PASSWORD': config("PASSWORD"),
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': config("NAME"),
        'USER': 'arjun',
        'PASSWORD': config("PASSWORD"),
        'HOST': 'gearup.c3as44es22h5.ap-southeast-2.rds.amazonaws.com',
        'PORT': '5432',
    }
}


EMAIL_BACKEND = config("EMAIL_BACKEND")
EMAIL_HOST = config("EMAIL_HOST")
EMAIL_PORT = config("EMAIL_PORT", cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL")



LOGIN_REDIRECT_URL = 'home'
ACCOUNT_LOGOUT_REDIRECT_URL = 'login'
LOGIN_URL = 'login'
LOGOUT_URL = 'logout'

ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGIN_METHODS = {'username', 'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': config("GOOGLE_CLIENT_ID"),
            'secret': config("GOOGLE_CLIENT_SECRET"),
        }
    }
}
SITE_ID = 1


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]



LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static'
]
STATIC_ROOT = BASE_DIR / 'staticfiles'



MEDIA_URL = 'https://res.cloudinary.com/dhpo5iq3m/image/upload/'
# MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

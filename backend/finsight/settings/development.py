from .base import *

DEBUG = True

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Looser throttling for local dev
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': '200/minute',
    'user': '1000/minute',
    'auth': '50/minute',
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO'},
        'apps': {'handlers': ['console'], 'level': 'DEBUG'},
    },
}

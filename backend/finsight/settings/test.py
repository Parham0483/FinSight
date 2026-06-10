"""Settings for the test suite.

Inherits development config but swaps in fast, deterministic behaviour:
a fast password hasher, locmem email, and an in-memory Celery eager mode so
tasks run synchronously instead of needing a broker.
"""
from .development import *  # noqa: F401,F403

# Fast password hashing — tests create many users.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Run Celery tasks synchronously in-process during tests.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Loosen throttling so functional tests aren't rate-limited.
REST_FRAMEWORK = {**REST_FRAMEWORK, 'DEFAULT_THROTTLE_RATES': {  # noqa: F405
    'anon': '10000/minute',
    'user': '10000/minute',
    'auth': '10000/minute',
}}

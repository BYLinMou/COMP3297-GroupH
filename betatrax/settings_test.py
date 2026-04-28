import os

os.environ['ENABLE_DJANGO_TENANTS'] = 'False'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

from betatrax.settings import *  # noqa: F401, F403, E402

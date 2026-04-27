from django.conf import settings
from django.db import connection
from django.db.utils import OperationalError, ProgrammingError
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from tenancy.utils import is_public_schema_context

from .models import Product
from .services import ensure_demo_seed


def _defect_tables_ready() -> bool:
    try:
        return Product._meta.db_table in connection.introspection.table_names()
    except (OperationalError, ProgrammingError):
        return False


def _should_seed_demo_data(sender) -> bool:
    if getattr(sender, "name", "") != "defects":
        return False
    if getattr(settings, "USE_DJANGO_TENANTS", False) and is_public_schema_context():
        return False
    return _defect_tables_ready()


@receiver(post_migrate)
def seed_demo_data(sender, **kwargs):
    if not _should_seed_demo_data(sender):
        return
    ensure_demo_seed()

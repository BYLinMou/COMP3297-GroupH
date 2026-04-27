from django.conf import settings
from django.db import connection

try:
    from django_tenants.utils import get_public_schema_name
except Exception:  # pragma: no cover - fallback for environments without django-tenants

    def get_public_schema_name() -> str:
        return "public"


def current_schema_name(request=None) -> str:
    tenant = getattr(request, "tenant", None)
    request_schema = getattr(tenant, "schema_name", "")
    if request_schema:
        return request_schema
    return getattr(connection, "schema_name", "")


def is_public_schema_context(request=None) -> bool:
    if not getattr(settings, "USE_DJANGO_TENANTS", False):
        return True
    return current_schema_name(request) == get_public_schema_name()

import re
from contextlib import nullcontext

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Domain, Tenant

try:
    from django_tenants.utils import schema_context
except Exception:  # pragma: no cover - django-tenants is optional outside tenant mode
    schema_context = None


SCHEMA_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,62}$")
DOMAIN_RE = re.compile(
    r"^(?=.{3,255}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$"
)


def _tenant_schema_context(tenant: Tenant):
    if getattr(settings, "USE_DJANGO_TENANTS", False) and schema_context is not None:
        return schema_context(tenant.schema_name)
    return nullcontext()


@transaction.atomic
def register_tenant(schema_name: str, domain: str, name: str = "") -> Tenant:
    normalized_schema = (schema_name or "").strip().lower()
    normalized_domain = (domain or "").strip().lower()
    normalized_name = (name or "").strip()

    if not normalized_schema:
        raise ValidationError("schema_name cannot be empty.")
    if normalized_schema in {"public", "information_schema"}:
        raise ValidationError("schema_name cannot use reserved names.")
    if not SCHEMA_NAME_RE.match(normalized_schema):
        raise ValidationError(
            "Invalid schema_name format. Use lowercase letters, digits, and underscores, and start with a letter."
        )

    if not normalized_domain:
        raise ValidationError("domain cannot be empty.")
    if not DOMAIN_RE.match(normalized_domain):
        raise ValidationError("Invalid domain format. Please provide a valid domain name.")

    if Tenant.objects.filter(schema_name=normalized_schema).exists():
        raise ValidationError("schema_name already exists.")
    if (
        Tenant.objects.filter(domain=normalized_domain).exists()
        or Domain.objects.filter(domain=normalized_domain).exists()
    ):
        raise ValidationError("domain already exists.")

    tenant = Tenant.objects.create(
        schema_name=normalized_schema,
        domain=normalized_domain,
        name=normalized_name,
    )
    Domain.objects.get_or_create(
        domain=normalized_domain,
        defaults={"tenant": tenant, "is_primary": True},
    )
    return tenant


@transaction.atomic
def add_tenant_domain(tenant: Tenant, domain: str, is_primary: bool = False) -> Domain:
    normalized_domain = (domain or "").strip().lower()
    if not normalized_domain:
        raise ValidationError("domain cannot be empty.")
    if not DOMAIN_RE.match(normalized_domain):
        raise ValidationError("Invalid domain format. Please provide a valid domain name.")
    if Tenant.objects.filter(domain=normalized_domain).exists():
        raise ValidationError("domain already exists.")
    if Domain.objects.filter(domain=normalized_domain).exists():
        raise ValidationError("domain already exists.")

    return Domain.objects.create(
        domain=normalized_domain,
        tenant=tenant,
        is_primary=is_primary,
    )


def create_tenant_admin_user(tenant: Tenant, username: str, email: str = "", password: str = ""):
    normalized_username = (username or "").strip()
    normalized_email = (email or "").strip()
    raw_password = password or ""

    if not normalized_username:
        raise ValidationError("tenant_admin_username cannot be empty.")
    if not raw_password:
        raise ValidationError("tenant_admin_password cannot be empty.")

    with _tenant_schema_context(tenant):
        user_model = get_user_model()
        if user_model.objects.filter(username=normalized_username).exists():
            raise ValidationError("tenant admin username already exists.")
        user = user_model.objects.create_user(
            username=normalized_username,
            email=normalized_email,
            password=raw_password,
        )
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])
        return user

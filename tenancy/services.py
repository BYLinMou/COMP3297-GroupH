import re

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Domain, Tenant


SCHEMA_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,62}$")
DOMAIN_RE = re.compile(
    r"^(?=.{3,255}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$"
)


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

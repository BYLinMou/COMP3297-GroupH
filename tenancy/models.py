from django.db import models
from django.utils import timezone

try:
    from django_tenants.models import DomainMixin, TenantMixin
except ImportError:  # pragma: no cover - exercised only without optional dependency
    DomainMixin = None

    class TenantMixin(models.Model):
        schema_name = models.CharField(max_length=63, unique=True, db_index=True)

        class Meta:
            abstract = True


class Tenant(TenantMixin):
    domain = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    auto_create_schema = True

    class Meta:
        ordering = ["schema_name"]

    def __str__(self) -> str:
        return f"{self.schema_name} ({self.domain})"


if DomainMixin is not None:

    class Domain(DomainMixin):
        class Meta:
            ordering = ["domain"]

else:  # pragma: no cover - exercised only without optional dependency

    class Domain(models.Model):
        domain = models.CharField(max_length=253, unique=True, db_index=True)
        tenant = models.ForeignKey(Tenant, db_index=True, related_name="domains", on_delete=models.CASCADE)
        is_primary = models.BooleanField(default=True, db_index=True)

        class Meta:
            ordering = ["domain"]

        def __str__(self) -> str:
            return self.domain

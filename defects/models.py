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


class Product(models.Model):
    product_id = models.CharField(max_length=32, primary_key=True)
    name = models.CharField(max_length=128, blank=True)
    owner_id = models.CharField(max_length=64)

    def __str__(self) -> str:
        return self.product_id


class ProductDeveloper(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="developers")
    developer_id = models.CharField(max_length=64, unique=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "developer_id"], name="uniq_product_developer"),
        ]

    def __str__(self) -> str:
        return f"{self.developer_id}@{self.product_id}"


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
        pass
else:
    class Domain(models.Model):
        domain = models.CharField(max_length=253, unique=True, db_index=True)
        tenant = models.ForeignKey(Tenant, db_index=True, related_name="domains", on_delete=models.CASCADE)
        is_primary = models.BooleanField(default=True, db_index=True)

        def __str__(self) -> str:
            return self.domain


class DefectStatus(models.TextChoices):
    NEW = "New", "New"
    OPEN = "Open", "Open"
    ASSIGNED = "Assigned", "Assigned"
    FIXED = "Fixed", "Fixed"
    RESOLVED = "Resolved", "Resolved"
    REJECTED = "Rejected", "Rejected"
    DUPLICATE = "Duplicate", "Duplicate"
    CANNOT_REPRODUCE = "Cannot Reproduce", "Cannot Reproduce"
    REOPENED = "Reopened", "Reopened"


class Severity(models.TextChoices):
    HIGH = "High", "High"
    MEDIUM = "Medium", "Medium"
    LOW = "Low", "Low"


class Priority(models.TextChoices):
    P1 = "P1", "P1"
    P2 = "P2", "P2"
    P3 = "P3", "P3"


class DefectReport(models.Model):
    report_id = models.CharField(max_length=32, primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="defects")
    version = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    description = models.TextField()
    steps = models.TextField()
    tester_id = models.CharField(max_length=64)
    tester_email = models.EmailField(blank=True)

    status = models.CharField(max_length=32, choices=DefectStatus.choices, default=DefectStatus.NEW)
    severity = models.CharField(max_length=16, choices=Severity.choices, blank=True)
    priority = models.CharField(max_length=8, choices=Priority.choices, blank=True)
    backlog_ref = models.CharField(max_length=64, blank=True)
    assignee_id = models.CharField(max_length=64, blank=True)
    duplicate_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duplicates",
    )
    fix_note = models.TextField(blank=True)
    retest_note = models.TextField(blank=True)

    received_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.report_id


class DefectComment(models.Model):
    defect = models.ForeignKey(DefectReport, on_delete=models.CASCADE, related_name="comments")
    author_id = models.CharField(max_length=64)
    text = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "id"]


class DefectStatusHistory(models.Model):
    defect = models.ForeignKey(DefectReport, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=32, choices=DefectStatus.choices)
    to_status = models.CharField(max_length=32, choices=DefectStatus.choices)
    actor_id = models.CharField(max_length=64, blank=True)
    changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["changed_at", "id"]

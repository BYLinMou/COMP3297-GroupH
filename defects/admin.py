from django.contrib import admin
from django.conf import settings

from tenancy.utils import is_public_schema_context

from .models import DefectComment, DefectReport, DefectStatusHistory, Product, ProductDeveloper


class TenantSchemaOnlyAdminMixin:
    def _is_tenant_schema(self, request) -> bool:
        if not getattr(settings, "USE_DJANGO_TENANTS", False):
            return True
        return not is_public_schema_context(request)

    def has_module_permission(self, request) -> bool:
        return self._is_tenant_schema(request) and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None) -> bool:
        return self._is_tenant_schema(request) and super().has_view_permission(request, obj)

    def has_add_permission(self, request) -> bool:
        return self._is_tenant_schema(request) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None) -> bool:
        return self._is_tenant_schema(request) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None) -> bool:
        return self._is_tenant_schema(request) and super().has_delete_permission(request, obj)


@admin.register(Product)
class ProductAdmin(TenantSchemaOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("product_id", "name", "owner_id")
    search_fields = ("product_id", "owner_id", "name")


@admin.register(ProductDeveloper)
class ProductDeveloperAdmin(TenantSchemaOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("developer_id", "product")
    search_fields = ("developer_id", "product__product_id")
    list_filter = ("product",)


@admin.register(DefectReport)
class DefectReportAdmin(TenantSchemaOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("report_id", "product", "status", "severity", "priority", "assignee_id", "tester_id")
    list_filter = ("status", "severity", "priority", "product")
    search_fields = ("report_id", "title", "product__product_id", "tester_id", "assignee_id")


@admin.register(DefectComment)
class DefectCommentAdmin(TenantSchemaOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("defect", "author_id", "created_at")
    search_fields = ("defect__report_id", "author_id", "text")


@admin.register(DefectStatusHistory)
class DefectStatusHistoryAdmin(TenantSchemaOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("defect", "from_status", "to_status", "actor_id", "changed_at")
    list_filter = ("from_status", "to_status")
    search_fields = ("defect__report_id", "actor_id")

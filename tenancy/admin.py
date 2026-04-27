from django.contrib import admin

from .models import Domain, Tenant
from .utils import is_public_schema_context


class PublicSchemaOnlyAdminMixin:
    def _is_public_schema(self, request) -> bool:
        return is_public_schema_context(request)

    def has_module_permission(self, request) -> bool:
        return self._is_public_schema(request) and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None) -> bool:
        return self._is_public_schema(request) and super().has_view_permission(request, obj)

    def has_add_permission(self, request) -> bool:
        return self._is_public_schema(request) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None) -> bool:
        return self._is_public_schema(request) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None) -> bool:
        return self._is_public_schema(request) and super().has_delete_permission(request, obj)


@admin.register(Tenant)
class TenantAdmin(PublicSchemaOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("schema_name", "domain", "name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("schema_name", "domain", "name")


@admin.register(Domain)
class DomainAdmin(PublicSchemaOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("domain", "tenant", "is_primary")
    list_filter = ("is_primary",)
    search_fields = ("domain", "tenant__schema_name")

from types import SimpleNamespace

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from defects.admin import ProductAdmin
from defects.models import Product

from .admin import DomainAdmin, TenantAdmin
from .models import Domain, Tenant
from .utils import is_public_schema_context
from .views import TenantRegisterApi


class TenantAdminVisibilityTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/admin/")
        self.request.user = get_user_model().objects.create_superuser(
            username="platform-admin",
            email="platform-admin@example.com",
            password="Pass1234!",
        )

    def test_tenant_admin_is_visible_outside_tenant_mode(self):
        tenant_admin = TenantAdmin(Tenant, admin.site)
        domain_admin = DomainAdmin(Domain, admin.site)

        self.assertTrue(tenant_admin.has_module_permission(self.request))
        self.assertTrue(domain_admin.has_module_permission(self.request))
        self.assertTrue(tenant_admin.has_add_permission(self.request))
        self.assertTrue(tenant_admin.has_delete_permission(self.request))

    @override_settings(USE_DJANGO_TENANTS=True)
    def test_tenant_admin_is_hidden_inside_tenant_schema(self):
        self.request.tenant = SimpleNamespace(schema_name="local")
        tenant_admin = TenantAdmin(Tenant, admin.site)
        domain_admin = DomainAdmin(Domain, admin.site)

        self.assertFalse(tenant_admin.has_module_permission(self.request))
        self.assertFalse(domain_admin.has_module_permission(self.request))
        self.assertFalse(tenant_admin.has_view_permission(self.request))
        self.assertFalse(domain_admin.has_change_permission(self.request))
        self.assertFalse(tenant_admin.has_add_permission(self.request))
        self.assertFalse(domain_admin.has_delete_permission(self.request))

    @override_settings(USE_DJANGO_TENANTS=True)
    def test_tenant_admin_is_visible_in_public_schema(self):
        self.request.tenant = SimpleNamespace(schema_name="public")
        tenant_admin = TenantAdmin(Tenant, admin.site)

        self.assertTrue(tenant_admin.has_module_permission(self.request))


class TenantScopedAdminVisibilityTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/admin/")
        self.request.user = get_user_model().objects.create_superuser(
            username="tenant-admin",
            email="tenant-admin@example.com",
            password="Pass1234!",
        )
        self.product_admin = ProductAdmin(Product, admin.site)

    def test_tenant_scoped_admin_is_visible_outside_tenant_mode(self):
        self.assertTrue(self.product_admin.has_module_permission(self.request))
        self.assertTrue(self.product_admin.has_view_permission(self.request))
        self.assertTrue(self.product_admin.has_add_permission(self.request))
        self.assertTrue(self.product_admin.has_change_permission(self.request))
        self.assertTrue(self.product_admin.has_delete_permission(self.request))

    @override_settings(USE_DJANGO_TENANTS=True)
    def test_tenant_scoped_admin_is_hidden_in_public_schema(self):
        self.request.tenant = SimpleNamespace(schema_name="public")

        self.assertFalse(self.product_admin.has_module_permission(self.request))
        self.assertFalse(self.product_admin.has_view_permission(self.request))
        self.assertFalse(self.product_admin.has_add_permission(self.request))
        self.assertFalse(self.product_admin.has_change_permission(self.request))
        self.assertFalse(self.product_admin.has_delete_permission(self.request))

    @override_settings(USE_DJANGO_TENANTS=True)
    def test_tenant_scoped_admin_is_visible_inside_tenant_schema(self):
        self.request.tenant = SimpleNamespace(schema_name="local")

        self.assertTrue(self.product_admin.has_module_permission(self.request))


class TenantRegisterSchemaGuardTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin_user = get_user_model().objects.create_superuser(
            username="schema-admin",
            email="schema-admin@example.com",
            password="Pass1234!",
        )

    @override_settings(USE_DJANGO_TENANTS=True)
    def test_register_tenant_api_is_not_available_inside_tenant_schema(self):
        request = self.factory.post(
            reverse("api-tenant-register-root"),
            {"schema_name": "team_x", "domain": "team-x.example.com"},
            format="json",
        )
        request.tenant = SimpleNamespace(schema_name="local")
        force_authenticate(request, user=self.admin_user)

        response = TenantRegisterApi.as_view()(request)

        self.assertEqual(response.status_code, 404)
        self.assertIn("public schema", response.data["error"])


class TenantSchemaUtilityTests(TestCase):
    @override_settings(USE_DJANGO_TENANTS=True)
    def test_missing_request_tenant_uses_connection_schema_fallback(self):
        self.assertFalse(is_public_schema_context())

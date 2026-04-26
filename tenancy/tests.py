from types import SimpleNamespace

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from defects.authz import ROLE_PLATFORM_ADMIN
from defects.admin import ProductAdmin
from defects.models import Product

from .middleware import PublicDomainTenantMiddleware
from .admin import DomainAdmin, TenantAdmin
from .models import Domain, Tenant
from .services import add_tenant_domain
from .utils import is_public_schema_context
from .views import TenantRegisterApi, platform_tenant_list


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


class PublicDomainTenantMiddlewareTests(TestCase):
    def setUp(self):
        self.middleware = PublicDomainTenantMiddleware(lambda request: None)
        self.factory = RequestFactory()

    @override_settings(PUBLIC_SCHEMA_DOMAINS=["platform.localhost"], PUBLIC_SCHEMA_URLCONF="betatrax.public_urls")
    def test_configured_public_domain_uses_public_urlconf(self):
        request = self.factory.get("/", HTTP_HOST="platform.localhost")

        result = self.middleware.no_tenant_found(request, "platform.localhost")

        self.assertIsNone(result)
        self.assertEqual(request.urlconf, "betatrax.public_urls")

    @override_settings(PUBLIC_SCHEMA_DOMAINS=["platform.localhost"])
    def test_unconfigured_missing_tenant_host_raises_404(self):
        request = self.factory.get("/", HTTP_HOST="unknown.localhost")

        with self.assertRaises(Http404):
            self.middleware.no_tenant_found(request, "unknown.localhost")

    @override_settings(
        PUBLIC_SCHEMA_DOMAINS=[],
        SHOW_PUBLIC_IF_NO_TENANT_FOUND=True,
        PUBLIC_SCHEMA_URLCONF="betatrax.public_urls",
    )
    def test_without_public_domains_uses_standard_public_fallback(self):
        request = self.factory.get("/", HTTP_HOST="missing.localhost")

        result = self.middleware.no_tenant_found(request, "missing.localhost")

        self.assertIsNone(result)
        self.assertEqual(request.urlconf, "betatrax.public_urls")


class TenantDomainServiceTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(schema_name="team_a", domain="team-a.example.com")

    def test_add_tenant_domain_validates_and_persists(self):
        with self.assertRaisesMessage(Exception, "domain cannot be empty."):
            add_tenant_domain(self.tenant, "")
        with self.assertRaisesMessage(Exception, "Invalid domain format"):
            add_tenant_domain(self.tenant, "invalid_domain")
        with self.assertRaisesMessage(Exception, "domain already exists."):
            add_tenant_domain(self.tenant, self.tenant.domain)

        domain = add_tenant_domain(self.tenant, "app.team-a.example.com", is_primary=True)

        self.assertEqual(domain.domain, "app.team-a.example.com")
        self.assertTrue(domain.is_primary)

        with self.assertRaisesMessage(Exception, "domain already exists."):
            add_tenant_domain(self.tenant, "app.team-a.example.com")


@override_settings(ROOT_URLCONF="betatrax.public_urls", PUBLIC_SCHEMA_DOMAINS=["platform.localhost"])
class PlatformTenantConsoleTests(TestCase):
    password = "Pass1234!"

    def setUp(self):
        self.factory = RequestFactory()
        self.url = reverse("platform-tenant-list")
        self.user_model = get_user_model()
        self.admin_user = self.user_model.objects.create_superuser(
            username="platform-console-admin",
            email="console-admin@example.com",
            password=self.password,
        )

    def test_platform_home_redirects_to_tenant_console(self):
        response = self.client.get(reverse("platform-home"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.url)

    def test_tenant_console_requires_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/platform/login/", response.url)

    def test_tenant_console_denies_non_platform_admin(self):
        user = self.user_model.objects.create_user(username="viewer", password=self.password)
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    @override_settings(USE_DJANGO_TENANTS=True)
    def test_tenant_console_denies_tenant_schema_context(self):
        request = self.factory.get(self.url)
        request.user = self.admin_user
        request.tenant = SimpleNamespace(schema_name="local")

        with self.assertRaises(PermissionDenied):
            platform_tenant_list(request)

    def test_tenant_console_lists_public_domains_and_tenants(self):
        Tenant.objects.create(schema_name="team_a", domain="team-a.example.com", name="Team A")
        self.client.force_login(self.admin_user)

        response = self.client.get(self.url)

        self.assertContains(response, "Tenant Console")
        self.assertContains(response, "platform.localhost")
        self.assertContains(response, "team_a")

    def test_tenant_console_creates_tenant_and_adds_domain(self):
        self.client.force_login(self.admin_user)

        create_response = self.client.post(
            self.url,
            {
                "action": "create_tenant",
                "schema_name": "team_blue",
                "domain": "team-blue.example.com",
                "name": "Team Blue",
            },
        )
        self.assertEqual(create_response.status_code, 302)
        tenant = Tenant.objects.get(schema_name="team_blue")
        self.assertTrue(Domain.objects.filter(domain="team-blue.example.com", tenant=tenant).exists())

        add_response = self.client.post(
            self.url,
            {
                "action": "add_domain",
                "tenant_id": tenant.pk,
                "domain": "bugs.team-blue.example.com",
                "is_primary": "on",
            },
        )
        self.assertEqual(add_response.status_code, 302)
        self.assertTrue(Domain.objects.filter(domain="bugs.team-blue.example.com", tenant=tenant).exists())

    def test_tenant_console_handles_invalid_posts(self):
        self.client.force_login(self.admin_user)

        unknown_response = self.client.post(self.url, {"action": "bad"}, follow=True)
        self.assertContains(unknown_response, "Unknown platform action.")

        invalid_create = self.client.post(
            self.url,
            {"action": "create_tenant", "schema_name": "", "domain": "invalid"},
            follow=True,
        )
        self.assertContains(invalid_create, "schema_name cannot be empty.")

        missing_tenant = self.client.post(
            self.url,
            {"action": "add_domain", "tenant_id": "9999", "domain": "app.example.com"},
            follow=True,
        )
        self.assertContains(missing_tenant, "Tenant not found.")

        tenant = Tenant.objects.create(schema_name="team_red", domain="team-red.example.com")
        invalid_domain = self.client.post(
            self.url,
            {"action": "add_domain", "tenant_id": tenant.pk, "domain": "invalid"},
            follow=True,
        )
        self.assertContains(invalid_domain, "Invalid domain format")

    def test_platform_login_handles_authentication_paths(self):
        login_url = reverse("platform-login")
        platform_group, _ = Group.objects.get_or_create(name=ROLE_PLATFORM_ADMIN)
        platform_user = self.user_model.objects.create_user(
            username="platform-group-user",
            password=self.password,
        )
        platform_user.groups.add(platform_group)
        viewer = self.user_model.objects.create_user(username="plain-viewer", password=self.password)

        get_response = self.client.get(login_url)
        self.assertContains(get_response, "Tenant administration")

        bad_password = self.client.post(
            login_url,
            {"username": platform_user.username, "password": "wrong"},
            follow=True,
        )
        self.assertContains(bad_password, "Invalid username or password.")

        forbidden = self.client.post(
            login_url,
            {"username": viewer.username, "password": self.password},
            follow=True,
        )
        self.assertContains(forbidden, "Only platform admins")

        success = self.client.post(
            login_url,
            {"username": platform_user.username, "password": self.password, "next": self.url},
        )
        self.assertEqual(success.status_code, 302)
        self.assertEqual(success.url, self.url)

        already_authenticated = self.client.get(login_url)
        self.assertEqual(already_authenticated.status_code, 302)
        self.assertEqual(already_authenticated.url, self.url)

    def test_platform_logout_clears_session(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("platform-logout"), follow=True)

        self.assertContains(response, "Signed out.")
        self.assertContains(response, "Sign In")

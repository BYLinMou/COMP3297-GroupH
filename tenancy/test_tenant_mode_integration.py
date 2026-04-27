from types import SimpleNamespace
from unittest import skipUnless

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test import override_settings
from django.urls import reverse
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import get_public_schema_name, schema_context
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from defects.authz import ROLE_DEVELOPER, ROLE_OWNER, ROLE_PLATFORM_ADMIN
from defects.models import DefectReport, DefectStatus, Product, ProductDeveloper
from tenancy.views import TenantRegisterApi


@skipUnless(settings.USE_DJANGO_TENANTS, "Tenant integration tests require ENABLE_DJANGO_TENANTS=True.")
@override_settings(
    ALLOWED_HOSTS=["testserver", "tenant.test.com", "platform.test.com"],
    PUBLIC_SCHEMA_DOMAINS=["platform.test.com"],
)
class TenantModeIntegrationTests(TenantTestCase):
    password = "Pass1234!"

    @classmethod
    def get_test_schema_name(cls):
        return "tenant_test"

    @classmethod
    def get_test_tenant_domain(cls):
        return "tenant.test.com"

    @classmethod
    def setup_tenant(cls, tenant):
        tenant.domain = cls.get_test_tenant_domain()
        tenant.name = "Tenant Test"

    @classmethod
    def setup_domain(cls, domain):
        domain.is_primary = True

    def setUp(self):
        connection.set_tenant(self.tenant)
        self.client = APIClient()
        self.owner_group, _ = Group.objects.get_or_create(name=ROLE_OWNER)
        self.developer_group, _ = Group.objects.get_or_create(name=ROLE_DEVELOPER)
        self.owner = self._create_user("tenant-owner", self.owner_group)
        self.developer = self._create_user("tenant-dev", self.developer_group)
        self.product = Product.objects.create(
            product_id="TenantProd",
            name="Tenant Product",
            owner_id=self.owner.username,
        )
        ProductDeveloper.objects.create(product=self.product, developer_id=self.developer.username)

    def _create_user(self, username, group):
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(username=username)
        if created:
            user.set_password(self.password)
            user.save(update_fields=["password"])
        user.groups.add(group)
        return user

    def test_tenant_host_can_create_and_list_defects_inside_tenant_schema(self):
        create_response = self.client.post(
            reverse("defects:api-create-defect"),
            {
                "product_id": self.product.product_id,
                "version": "2.0.0",
                "title": "Tenant scoped bug",
                "description": "Tenant-only defect",
                "steps": "Open tenant app",
                "tester_id": "tenant-tester",
            },
            format="json",
            HTTP_HOST=self.get_test_tenant_domain(),
        )

        self.assertEqual(create_response.status_code, 201)
        report_id = create_response.json()["report_id"]
        self.assertTrue(DefectReport.objects.filter(report_id=report_id, status=DefectStatus.NEW).exists())

        self.client.force_authenticate(user=self.owner)
        list_response = self.client.get(
            reverse("defects:api-list-defects"),
            HTTP_HOST=self.get_test_tenant_domain(),
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertTrue(
            any(item["report_id"] == report_id for item in list_response.json()["items"])
        )

    def test_tenant_models_exist_in_tenant_schema_not_public_schema(self):
        tenant_tables = set(connection.introspection.table_names())
        self.assertIn("defects_product", tenant_tables)

        with schema_context(get_public_schema_name()):
            public_tables = set(connection.introspection.table_names())

        self.assertNotIn("defects_product", public_tables)

    def test_public_schema_can_register_tenant(self):
        with schema_context(get_public_schema_name()):
            platform_group, _ = Group.objects.get_or_create(name=ROLE_PLATFORM_ADMIN)
            platform_user = get_user_model().objects.create_user(
                username="platform-api-admin",
                password=self.password,
            )
            platform_user.groups.add(platform_group)

        connection.set_schema_to_public()
        request = APIRequestFactory().post(
            reverse("api-tenant-register-root"),
            {
                "schema_name": "api_team",
                "domain": "api-team.test.com",
                "name": "API Team",
            },
            format="json",
        )
        request.tenant = SimpleNamespace(schema_name=get_public_schema_name())
        force_authenticate(request, user=platform_user)
        response = TenantRegisterApi.as_view()(request)
        connection.set_tenant(self.tenant)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["tenant"]["schema_name"], "api_team")

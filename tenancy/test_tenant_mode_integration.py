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

    def _create_defect(self, title="Tenant scoped bug", tester_id="tenant-tester"):
        response = self.client.post(
            reverse("defects:api-create-defect"),
            {
                "product_id": self.product.product_id,
                "version": "2.0.0",
                "title": title,
                "description": "Tenant-only defect",
                "steps": "Open tenant app",
                "tester_id": tester_id,
            },
            format="json",
            HTTP_HOST=self.get_test_tenant_domain(),
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["report_id"]

    def _action(self, defect_id, payload, user):
        self.client.force_authenticate(user=user)
        return self.client.post(
            reverse("defects:api-defect-action", kwargs={"defect_id": defect_id}),
            payload,
            format="json",
            HTTP_HOST=self.get_test_tenant_domain(),
        )

    def test_tenant_host_can_create_and_list_defects_inside_tenant_schema(self):
        report_id = self._create_defect()
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

    def test_tenant_lifecycle_actions_work_inside_tenant_schema(self):
        defect_id = self._create_defect(title="Tenant lifecycle defect", tester_id="tenant-lifecycle")

        accept_response = self._action(
            defect_id,
            {"action": "accept_open", "severity": "High", "priority": "P1"},
            self.owner,
        )
        self.assertEqual(accept_response.status_code, 200)
        self.assertEqual(accept_response.json()["status"], DefectStatus.OPEN)

        take_response = self._action(defect_id, {"action": "take_ownership"}, self.developer)
        self.assertEqual(take_response.status_code, 200)
        self.assertEqual(take_response.json()["status"], DefectStatus.ASSIGNED)

        fixed_response = self._action(
            defect_id,
            {"action": "set_fixed", "fix_note": "tenant patch applied"},
            self.developer,
        )
        self.assertEqual(fixed_response.status_code, 200)
        self.assertEqual(fixed_response.json()["status"], DefectStatus.FIXED)

        reopen_response = self._action(
            defect_id,
            {"action": "reopen", "retest_note": "still reproducible in tenant env"},
            self.owner,
        )
        self.assertEqual(reopen_response.status_code, 200)
        self.assertEqual(reopen_response.json()["status"], DefectStatus.REOPENED)

        defect = DefectReport.objects.get(report_id=defect_id)
        self.assertEqual(defect.assignee_id, self.developer.username)
        self.assertEqual(defect.status, DefectStatus.REOPENED)
        self.assertEqual(defect.history.count(), 5)

    def test_tenant_developer_cannot_view_new_defect_detail(self):
        defect_id = self._create_defect(title="Tenant new detail", tester_id="tenant-detail")
        self.client.force_authenticate(user=self.developer)

        response = self.client.get(
            reverse("defects:api-defect-detail", kwargs={"defect_id": defect_id}),
            HTTP_HOST=self.get_test_tenant_domain(),
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("cannot access New", response.json()["error"])

    def test_tenant_owner_can_query_developer_effectiveness(self):
        for index in range(20):
            defect_id = self._create_defect(
                title=f"Tenant effectiveness {index}",
                tester_id=f"tenant-effect-{index}",
            )
            accept_response = self._action(
                defect_id,
                {"action": "accept_open", "severity": "High", "priority": "P1"},
                self.owner,
            )
            self.assertEqual(accept_response.status_code, 200)
            take_response = self._action(defect_id, {"action": "take_ownership"}, self.developer)
            self.assertEqual(take_response.status_code, 200)
            fixed_response = self._action(
                defect_id,
                {"action": "set_fixed", "fix_note": f"tenant fix {index}"},
                self.developer,
            )
            self.assertEqual(fixed_response.status_code, 200)

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(
            reverse("api-developer-effectiveness", kwargs={"developer_id": self.developer.username}),
            HTTP_HOST=self.get_test_tenant_domain(),
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["developer_id"], self.developer.username)
        self.assertEqual(body["fixed"], 20)
        self.assertEqual(body["reopened"], 0)
        self.assertEqual(body["classification"], "Good")

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

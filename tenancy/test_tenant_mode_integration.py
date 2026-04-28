from types import SimpleNamespace
from unittest import skipUnless

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
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

    def test_create_user_reuses_existing_tenant_user(self):
        reused = self._create_user(self.owner.username, self.developer_group)

        self.assertEqual(reused.pk, self.owner.pk)
        self.assertTrue(reused.groups.filter(name=ROLE_DEVELOPER).exists())

    def _create_defect(self, title="Tenant scoped bug", tester_id="tenant-tester", email=""):
        response = self.client.post(
            reverse("defects:api-create-defect"),
            {
                "product_id": self.product.product_id,
                "version": "2.0.0",
                "title": title,
                "description": "Tenant-only defect",
                "steps": "Open tenant app",
                "tester_id": tester_id,
                "email": email,
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

    def test_tenant_owner_can_reject_and_mark_duplicate(self):
        reject_id = self._create_defect(title="Tenant reject defect", tester_id="tenant-reject")
        reject_response = self._action(reject_id, {"action": "reject"}, self.owner)
        self.assertEqual(reject_response.status_code, 200)
        self.assertEqual(reject_response.json()["status"], DefectStatus.REJECTED)

        root_id = self._create_defect(title="Tenant root defect", tester_id="tenant-root")
        duplicate_id = self._create_defect(title="Tenant duplicate defect", tester_id="tenant-duplicate")
        duplicate_response = self._action(
            duplicate_id,
            {"action": "duplicate", "duplicate_of": root_id},
            self.owner,
        )
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertEqual(duplicate_response.json()["status"], DefectStatus.DUPLICATE)
        self.assertEqual(DefectReport.objects.get(report_id=duplicate_id).duplicate_of_id, root_id)

    def test_tenant_assigned_developer_can_mark_cannot_reproduce(self):
        defect_id = self._create_defect(title="Tenant cannot reproduce", tester_id="tenant-cannot")
        accept_response = self._action(
            defect_id,
            {"action": "accept_open", "severity": "High", "priority": "P1"},
            self.owner,
        )
        self.assertEqual(accept_response.status_code, 200)
        take_response = self._action(defect_id, {"action": "take_ownership"}, self.developer)
        self.assertEqual(take_response.status_code, 200)

        cannot_repro_response = self._action(
            defect_id,
            {"action": "cannot_reproduce", "fix_note": "cannot reproduce in tenant qa"},
            self.developer,
        )
        self.assertEqual(cannot_repro_response.status_code, 200)
        self.assertEqual(cannot_repro_response.json()["status"], DefectStatus.CANNOT_REPRODUCE)

    def test_tenant_list_filters_support_slug_status_values(self):
        cannot_repro_id = self._create_defect(title="Tenant list cannot repro", tester_id="tenant-list-cannot")
        self.client.force_authenticate(user=self.owner)
        self._action(
            cannot_repro_id,
            {"action": "accept_open", "severity": "High", "priority": "P1"},
            self.owner,
        )
        self._action(cannot_repro_id, {"action": "take_ownership"}, self.developer)
        self._action(
            cannot_repro_id,
            {"action": "cannot_reproduce", "fix_note": "tenant list cannot repro"},
            self.developer,
        )

        cannot_repro_list = self.client.get(
            reverse("defects:api-list-defects"),
            {"status": "cannot-reproduce"},
            HTTP_HOST=self.get_test_tenant_domain(),
        )
        self.assertEqual(cannot_repro_list.status_code, 200)
        self.assertTrue(any(item["report_id"] == cannot_repro_id for item in cannot_repro_list.json()["items"]))

        reopened_id = self._create_defect(title="Tenant list reopened", tester_id="tenant-list-reopen")
        self._action(
            reopened_id,
            {"action": "accept_open", "severity": "High", "priority": "P1"},
            self.owner,
        )
        self._action(reopened_id, {"action": "take_ownership"}, self.developer)
        self._action(reopened_id, {"action": "set_fixed", "fix_note": "tenant list fixed"}, self.developer)
        self._action(
            reopened_id,
            {"action": "reopen", "retest_note": "tenant list reopened"},
            self.owner,
        )

        reopened_list = self.client.get(
            reverse("defects:api-list-defects"),
            {"status": "reopened"},
            HTTP_HOST=self.get_test_tenant_domain(),
        )
        self.assertEqual(reopened_list.status_code, 200)
        self.assertTrue(any(item["report_id"] == reopened_id for item in reopened_list.json()["items"]))

    def test_tenant_non_owner_cannot_query_effectiveness_and_outsider_cannot_view_detail(self):
        defect_id = self._create_defect(title="Tenant outsider detail", tester_id="tenant-outsider")

        outsider = self._create_user("tenant-outsider-dev", self.developer_group)
        self.client.force_authenticate(user=outsider)
        outsider_response = self.client.get(
            reverse("defects:api-defect-detail", kwargs={"defect_id": defect_id}),
            HTTP_HOST=self.get_test_tenant_domain(),
        )
        self.assertEqual(outsider_response.status_code, 403)

        self.client.force_authenticate(user=self.developer)
        developer_effectiveness = self.client.get(
            reverse("api-developer-effectiveness", kwargs={"developer_id": self.developer.username}),
            HTTP_HOST=self.get_test_tenant_domain(),
        )
        self.assertEqual(developer_effectiveness.status_code, 403)

        self._action(
            defect_id,
            {"action": "accept_open", "severity": "High", "priority": "P1"},
            self.owner,
        )
        self.client.force_authenticate(user=outsider)
        outsider_open_detail = self.client.get(
            reverse("defects:api-defect-detail", kwargs={"defect_id": defect_id}),
            HTTP_HOST=self.get_test_tenant_domain(),
        )
        self.assertEqual(outsider_open_detail.status_code, 404)

    def test_tenant_outsider_developer_cannot_list_open_or_reopened_defects(self):
        outsider = self._create_user("tenant-outsider-list", self.developer_group)

        open_id = self._create_defect(title="Tenant outsider open", tester_id="tenant-outsider-open")
        self._action(open_id, {"action": "accept_open", "severity": "High", "priority": "P1"}, self.owner)

        reopened_id = self._create_defect(title="Tenant outsider reopened", tester_id="tenant-outsider-reopened")
        self._action(reopened_id, {"action": "accept_open", "severity": "High", "priority": "P1"}, self.owner)
        self._action(reopened_id, {"action": "take_ownership"}, self.developer)
        self._action(reopened_id, {"action": "set_fixed", "fix_note": "tenant outsider fixed"}, self.developer)
        self._action(reopened_id, {"action": "reopen", "retest_note": "tenant outsider reopened"}, self.owner)

        self.client.force_authenticate(user=outsider)
        open_response = self.client.get(
            reverse("defects:api-list-defects"),
            {"status": "Open", "developer_id": outsider.username},
            HTTP_HOST=self.get_test_tenant_domain(),
        )
        self.assertEqual(open_response.status_code, 200)
        self.assertEqual(open_response.json()["items"], [])

        reopened_response = self.client.get(
            reverse("defects:api-list-defects"),
            {"status": "reopened", "developer_id": outsider.username},
            HTTP_HOST=self.get_test_tenant_domain(),
        )
        self.assertEqual(reopened_response.status_code, 200)
        self.assertEqual(reopened_response.json()["items"], [])

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

    def test_tenant_root_status_change_notifies_duplicate_chain(self):
        root_id = self._create_defect(
            title="Tenant notify root",
            tester_id="tenant-notify-root",
            email="tenant-root@example.com",
        )
        duplicate_id = self._create_defect(
            title="Tenant notify child",
            tester_id="tenant-notify-child",
            email="tenant-child@example.com",
        )
        duplicate_response = self._action(
            duplicate_id,
            {"action": "duplicate", "duplicate_of": root_id},
            self.owner,
        )
        self.assertEqual(duplicate_response.status_code, 200)
        mail.outbox.clear()

        accept_response = self._action(
            root_id,
            {"action": "accept_open", "severity": "High", "priority": "P1"},
            self.owner,
        )
        self.assertEqual(accept_response.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)
        recipients = sorted(message.to[0] for message in mail.outbox)
        self.assertEqual(recipients, ["tenant-child@example.com", "tenant-root@example.com"])

    def test_tenant_invalid_accept_payload_and_wrong_actor_transitions(self):
        defect_id = self._create_defect(title="Tenant invalid accept", tester_id="tenant-invalid-accept")

        invalid_severity = self._action(
            defect_id,
            {"action": "accept_open", "severity": "Critical", "priority": "P1"},
            self.owner,
        )
        self.assertEqual(invalid_severity.status_code, 400)
        self.assertIn("Severity must be High, Medium, or Low", invalid_severity.json()["error"])

        invalid_priority = self._action(
            defect_id,
            {"action": "accept_open", "severity": "High", "priority": "P9"},
            self.owner,
        )
        self.assertEqual(invalid_priority.status_code, 400)
        self.assertIn("Priority must be P1, P2, or P3", invalid_priority.json()["error"])

        other_owner = self._create_user("tenant-other-owner", self.owner_group)
        wrong_owner_accept = self._action(
            defect_id,
            {"action": "accept_open", "severity": "High", "priority": "P1"},
            other_owner,
        )
        self.assertEqual(wrong_owner_accept.status_code, 400)
        self.assertIn("Only the Product Owner can accept", wrong_owner_accept.json()["error"])

        accept_response = self._action(
            defect_id,
            {"action": "accept_open", "severity": "High", "priority": "P1"},
            self.owner,
        )
        self.assertEqual(accept_response.status_code, 200)

        outsider_dev = self._create_user("tenant-outsider-action", self.developer_group)
        outsider_take = self._action(defect_id, {"action": "take_ownership"}, outsider_dev)
        self.assertEqual(outsider_take.status_code, 400)
        self.assertIn("Only developers on the product team", outsider_take.json()["error"])

    def test_tenant_multilevel_duplicate_chain_notifies_all_descendants(self):
        root_id = self._create_defect(
            title="Tenant chain root",
            tester_id="tenant-chain-root",
            email="tenant-chain-root@example.com",
        )
        child_id = self._create_defect(
            title="Tenant chain child",
            tester_id="tenant-chain-child",
            email="tenant-chain-child@example.com",
        )
        grandchild_id = self._create_defect(
            title="Tenant chain grandchild",
            tester_id="tenant-chain-grandchild",
            email="tenant-chain-grandchild@example.com",
        )
        self._action(child_id, {"action": "duplicate", "duplicate_of": root_id}, self.owner)
        DefectReport.objects.filter(report_id=grandchild_id).update(duplicate_of_id=child_id)
        mail.outbox.clear()

        accept_response = self._action(
            root_id,
            {"action": "accept_open", "severity": "High", "priority": "P1"},
            self.owner,
        )
        self.assertEqual(accept_response.status_code, 200)
        recipients = sorted(message.to[0] for message in mail.outbox)
        self.assertEqual(
            recipients,
            [
                "tenant-chain-child@example.com",
                "tenant-chain-grandchild@example.com",
                "tenant-chain-root@example.com",
            ],
        )

    def test_tenant_duplicate_chain_notifies_on_reject_and_reopen(self):
        reject_root_id = self._create_defect(
            title="Tenant reject root",
            tester_id="tenant-reject-root",
            email="tenant-reject-root@example.com",
        )
        reject_child_id = self._create_defect(
            title="Tenant reject child",
            tester_id="tenant-reject-child",
            email="tenant-reject-child@example.com",
        )
        self._action(reject_child_id, {"action": "duplicate", "duplicate_of": reject_root_id}, self.owner)
        mail.outbox.clear()
        reject_response = self._action(reject_root_id, {"action": "reject"}, self.owner)
        self.assertEqual(reject_response.status_code, 200)
        reject_recipients = sorted(message.to[0] for message in mail.outbox)
        self.assertEqual(reject_recipients, ["tenant-reject-child@example.com", "tenant-reject-root@example.com"])

        reopen_root_id = self._create_defect(
            title="Tenant reopen root",
            tester_id="tenant-reopen-root",
            email="tenant-reopen-root@example.com",
        )
        reopen_child_id = self._create_defect(
            title="Tenant reopen child",
            tester_id="tenant-reopen-child",
            email="tenant-reopen-child@example.com",
        )
        self._action(reopen_child_id, {"action": "duplicate", "duplicate_of": reopen_root_id}, self.owner)
        self._action(reopen_root_id, {"action": "accept_open", "severity": "High", "priority": "P1"}, self.owner)
        self._action(reopen_root_id, {"action": "take_ownership"}, self.developer)
        self._action(reopen_root_id, {"action": "set_fixed", "fix_note": "tenant reopen fixed"}, self.developer)
        mail.outbox.clear()
        reopen_response = self._action(
            reopen_root_id,
            {"action": "reopen", "retest_note": "tenant reopen retest failed"},
            self.owner,
        )
        self.assertEqual(reopen_response.status_code, 200)
        reopen_recipients = sorted(message.to[0] for message in mail.outbox)
        self.assertEqual(reopen_recipients, ["tenant-reopen-child@example.com", "tenant-reopen-root@example.com"])

    def test_tenant_non_root_duplicate_transition_does_not_notify_siblings(self):
        root_id = self._create_defect(
            title="Tenant sibling root",
            tester_id="tenant-sibling-root",
            email="tenant-sibling-root@example.com",
        )
        child_id = self._create_defect(
            title="Tenant sibling child",
            tester_id="tenant-sibling-child",
            email="tenant-sibling-child@example.com",
        )
        sibling_id = self._create_defect(
            title="Tenant sibling other",
            tester_id="tenant-sibling-other",
            email="tenant-sibling-other@example.com",
        )
        DefectReport.objects.filter(report_id=child_id).update(duplicate_of_id=root_id)
        DefectReport.objects.filter(report_id=sibling_id).update(duplicate_of_id=root_id)

        response = self._action(child_id, {"action": "duplicate", "duplicate_of": root_id}, self.owner)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["tenant-sibling-child@example.com"])

    def test_tenant_duplicate_without_email_is_skipped_in_chain_notification(self):
        root_id = self._create_defect(
            title="Tenant no-email root",
            tester_id="tenant-no-email-root",
            email="tenant-no-email-root@example.com",
        )
        duplicate_id = self._create_defect(
            title="Tenant no-email child",
            tester_id="tenant-no-email-child",
            email="",
        )
        duplicate_response = self._action(
            duplicate_id,
            {"action": "duplicate", "duplicate_of": root_id},
            self.owner,
        )
        self.assertEqual(duplicate_response.status_code, 200)

        accept_response = self._action(
            root_id,
            {"action": "accept_open", "severity": "High", "priority": "P1"},
            self.owner,
        )
        self.assertEqual(accept_response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["tenant-no-email-root@example.com"])

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

    @override_settings(
        ALLOWED_HOSTS=["testserver", "tenant.test.com", "platform.test.com", "api-team.test.com"],
        PUBLIC_SCHEMA_DOMAINS=["platform.test.com"],
    )
    def test_public_schema_registered_tenant_domain_can_use_defect_api(self):
        with schema_context(get_public_schema_name()):
            platform_group, _ = Group.objects.get_or_create(name=ROLE_PLATFORM_ADMIN)
            platform_user = get_user_model().objects.create_user(
                username="platform-e2e-admin",
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
        self.assertEqual(response.status_code, 201)

        with schema_context("api_team"):
            owner_group, _ = Group.objects.get_or_create(name=ROLE_OWNER)
            developer_group, _ = Group.objects.get_or_create(name=ROLE_DEVELOPER)
            owner = self._create_user("api-team-owner", owner_group)
            developer = self._create_user("api-team-dev", developer_group)
            product = Product.objects.create(
                product_id="ApiTeamProd",
                name="API Team Product",
                owner_id=owner.username,
            )
            ProductDeveloper.objects.create(product=product, developer_id=developer.username)

        create_response = self.client.post(
            reverse("defects:api-create-defect"),
            {
                "product_id": "ApiTeamProd",
                "version": "3.0.0",
                "title": "Registered tenant defect",
                "description": "Created via dynamically registered tenant domain",
                "steps": "Open app and submit form",
                "tester_id": "api-team-tester",
            },
            format="json",
            HTTP_HOST="api-team.test.com",
        )
        self.assertEqual(create_response.status_code, 201)
        defect_id = create_response.json()["report_id"]

        self.client.force_authenticate(user=owner)
        list_response = self.client.get(
            reverse("defects:api-list-defects"),
            HTTP_HOST="api-team.test.com",
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertTrue(any(item["report_id"] == defect_id for item in list_response.json()["items"]))

        detail_response = self.client.get(
            reverse("defects:api-defect-detail", kwargs={"defect_id": defect_id}),
            HTTP_HOST="api-team.test.com",
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["product_id"], "ApiTeamProd")

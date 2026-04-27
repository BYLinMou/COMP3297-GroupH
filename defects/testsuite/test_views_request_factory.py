from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from unittest import skipIf
from rest_framework.test import APIRequestFactory, force_authenticate

from defects.models import DefectStatus
from defects.views import (
    DefectActionApi,
    DefectDetailApi,
    DefectListApi,
    DeveloperEffectivenessApi,
)
from tenancy.views import TenantRegisterApi

from .base import DefectApiTestCase


@skipIf(settings.USE_DJANGO_TENANTS, "Single-schema request-factory tests run with ENABLE_DJANGO_TENANTS=False.")
class DefectRequestFactoryTests(DefectApiTestCase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

    def test_list_view_filters_to_authenticated_owner_product_scope(self):
        request = self.factory.get(self.list_url)
        force_authenticate(request, user=self.owner_user)
        response = DefectListApi.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["report_id"], self.seed_defect.report_id)

    def test_action_view_returns_403_for_anonymous_request(self):
        request = self.factory.post(
            self.action_url(self.seed_defect.report_id),
            {"action": "reject"},
            format="json",
        )
        request.user = AnonymousUser()
        response = DefectActionApi.as_view()(request, defect_id=self.seed_defect.report_id)
        self.assertEqual(response.status_code, 403)

    def test_detail_view_rejects_non_role_user_and_unknown_defect(self):
        outsider = self.create_user("viewer-002", "viewer2@example.com")

        request = self.factory.get(self.detail_url(self.seed_defect.report_id))
        force_authenticate(request, user=outsider)
        response = DefectDetailApi.as_view()(request, defect_id=self.seed_defect.report_id)
        self.assertEqual(response.status_code, 403)

        request = self.factory.get(self.detail_url("BT-RP-9999"))
        force_authenticate(request, user=self.owner_user)
        response = DefectDetailApi.as_view()(request, defect_id="BT-RP-9999")
        self.assertEqual(response.status_code, 404)

    def test_detail_view_hides_out_of_scope_owner_and_new_status_for_developer(self):
        other_owner = self.create_user("owner-404", "owner404@example.com", self.owner_group)

        request = self.factory.get(self.detail_url(self.seed_defect.report_id))
        force_authenticate(request, user=other_owner)
        response = DefectDetailApi.as_view()(request, defect_id=self.seed_defect.report_id)
        self.assertEqual(response.status_code, 404)

        self.seed_defect.status = DefectStatus.NEW
        self.seed_defect.save(update_fields=["status"])
        request = self.factory.get(self.detail_url(self.seed_defect.report_id))
        force_authenticate(request, user=self.dev_user)
        response = DefectDetailApi.as_view()(request, defect_id=self.seed_defect.report_id)
        self.assertEqual(response.status_code, 403)

    def test_action_view_rejects_authenticated_user_with_blank_actor_id(self):
        blank_user = self.create_user("   ", "blank@example.com", self.owner_group)
        request = self.factory.post(
            self.action_url(self.seed_defect.report_id),
            {"action": "reject"},
            format="json",
        )
        force_authenticate(request, user=blank_user)
        response = DefectActionApi.as_view()(request, defect_id=self.seed_defect.report_id)
        self.assertEqual(response.status_code, 403)

    def test_tenant_register_view_denies_non_platform_admin(self):
        request = self.factory.post(
            self.tenant_register_url,
            {"schema_name": "rf_team", "domain": "rf-team.example.com"},
            format="json",
        )
        force_authenticate(request, user=self.owner_user)
        response = TenantRegisterApi.as_view()(request)
        self.assertEqual(response.status_code, 403)

    def test_effectiveness_view_denies_non_owner_actor(self):
        request = self.factory.get(self.developer_effectiveness_url(self.dev_user.username))
        force_authenticate(request, user=self.dev_user)
        response = DeveloperEffectivenessApi.as_view()(request, developer_id=self.dev_user.username)
        self.assertEqual(response.status_code, 403)

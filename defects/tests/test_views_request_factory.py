from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory, force_authenticate

from defects.views import DefectActionApi, DefectListApi

from .base import DefectApiTestCase


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

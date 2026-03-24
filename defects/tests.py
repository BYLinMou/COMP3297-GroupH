import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from .models import DefectReport, DefectStatus
from .services import ensure_demo_seed


class DefectApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.create_url = reverse("defects:api-create-defect")
        self.list_url = reverse("defects:api-list-defects")
        ensure_demo_seed()

        owner_group = Group.objects.get(name="owner")
        developer_group = Group.objects.get(name="developer")
        user_model = get_user_model()

        self.owner_user = user_model.objects.get(username="owner-001")
        self.owner_user.groups.add(owner_group)

        self.dev_user = user_model.objects.get(username="dev-001")
        self.dev_user.groups.add(developer_group)

    def test_submit_defect_missing_required_fields_returns_400(self):
        response = self.client.post(
            self.create_url,
            data=json.dumps({"product_id": "PRD-1007"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["error"], "Missing required fields.")
        self.assertIn("title", body["missing_fields"])

    def test_submit_defect_unknown_product_returns_404(self):
        payload = {
            "product_id": "PRD-UNKNOWN",
            "version": "v1",
            "title": "Crash",
            "description": "desc",
            "steps": "steps",
            "tester_id": "tester-001",
        }
        response = self.client.post(
            self.create_url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "Unknown Product ID.")

    def test_submit_defect_success_stored_as_new(self):
        payload = {
            "product_id": "PRD-1007",
            "version": "v1.5.0-beta",
            "title": "UI glitch",
            "description": "visual issue",
            "steps": "1. open page",
            "tester_id": "tester-009",
        }
        response = self.client.post(
            self.create_url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        report_id = response.json()["report_id"]
        defect = DefectReport.objects.get(report_id=report_id)
        self.assertEqual(defect.status, DefectStatus.NEW)
        self.assertEqual(defect.tester_email, "")

    def test_list_requires_authentication(self):
        response = self.client.get(self.list_url, {"status": "Open"})
        self.assertEqual(response.status_code, 403)

    def test_list_open_defects_for_developer(self):
        self.client.force_login(self.dev_user)
        response = self.client.get(self.list_url, {"status": "Open", "developer_id": "dev-001"})
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertTrue(any(item["status"] == DefectStatus.OPEN for item in items))

    def test_developer_cannot_list_new(self):
        self.client.force_login(self.dev_user)
        response = self.client.get(self.list_url, {"status": "New"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("cannot access New", response.json()["error"])

    def test_take_ownership_requires_team_membership(self):
        user_model = get_user_model()
        outsider = user_model.objects.create_user(username="dev-999", password="Pass1234!")
        outsider.groups.add(Group.objects.get(name="developer"))
        self.client.force_login(outsider)
        action_url = reverse("defects:api-defect-action", kwargs={"defect_id": "BT-RP-2462"})
        response = self.client.post(
            action_url,
            data=json.dumps({"action": "take_ownership"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("product team", response.json()["error"])

    def test_lifecycle_open_to_assigned_to_fixed_to_resolved(self):
        action_url = reverse("defects:api-defect-action", kwargs={"defect_id": "BT-RP-2462"})
        self.client.force_login(self.dev_user)
        response = self.client.post(
            action_url,
            data=json.dumps({"action": "take_ownership"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.ASSIGNED)

        response = self.client.post(
            action_url,
            data=json.dumps({"action": "set_fixed", "fix_note": "patched"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.FIXED)

        self.client.force_login(self.owner_user)
        response = self.client.post(
            action_url,
            data=json.dumps({"action": "set_resolved", "retest_note": "verified"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.RESOLVED)

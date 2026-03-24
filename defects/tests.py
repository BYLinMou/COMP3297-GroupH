import json

from django.test import Client, TestCase
from django.urls import reverse

from .models import DefectReport, DefectStatus


class DefectApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.create_url = reverse("defects:api-create-defect")
        self.list_url = reverse("defects:api-list-defects")

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

    def test_list_open_defects_for_developer(self):
        response = self.client.get(self.list_url, {"status": "Open", "developer_id": "dev-001"})
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertTrue(any(item["status"] == DefectStatus.OPEN for item in items))

    def test_take_ownership_requires_team_membership(self):
        action_url = reverse("defects:api-defect-action", kwargs={"defect_id": "BT-RP-2462"})
        response = self.client.post(
            action_url,
            data=json.dumps({"action": "take_ownership", "developer_id": "dev-999"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("product team", response.json()["error"])

    def test_lifecycle_open_to_assigned_to_fixed_to_resolved(self):
        action_url = reverse("defects:api-defect-action", kwargs={"defect_id": "BT-RP-2462"})
        response = self.client.post(
            action_url,
            data=json.dumps({"action": "take_ownership", "developer_id": "dev-001"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.ASSIGNED)

        response = self.client.post(
            action_url,
            data=json.dumps({"action": "set_fixed", "developer_id": "dev-001", "fix_note": "patched"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.FIXED)

        response = self.client.post(
            action_url,
            data=json.dumps({"action": "set_resolved", "owner_id": "owner-001", "retest_note": "verified"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.RESOLVED)

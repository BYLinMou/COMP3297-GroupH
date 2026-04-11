import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from .models import DefectComment, DefectReport, DefectStatus, Product, ProductDeveloper


class DefectApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.create_url = reverse("defects:api-create-defect")
        self.list_url = reverse("defects:api-list-defects")
        self.register_url = reverse("api-product-register-root")
        self.detail_url = lambda defect_id: reverse("defects:api-defect-detail", kwargs={"defect_id": defect_id})

        owner_group, _ = Group.objects.get_or_create(name="owner")
        developer_group, _ = Group.objects.get_or_create(name="developer")
        user_model = get_user_model()

        self.owner_user, owner_created = user_model.objects.get_or_create(
            username="owner-001",
            defaults={"email": "owner001@example.com"},
        )
        if owner_created:
            self.owner_user.set_password("Pass1234!")
            self.owner_user.save(update_fields=["password"])
        self.owner_user.groups.add(owner_group)

        self.dev_user, dev_created = user_model.objects.get_or_create(
            username="dev-001",
            defaults={"email": "dev001@example.com"},
        )
        if dev_created:
            self.dev_user.set_password("Pass1234!")
            self.dev_user.save(update_fields=["password"])
        self.dev_user.groups.add(developer_group)

        self.owner_group = owner_group
        self.developer_group = developer_group

        product, _ = Product.objects.get_or_create(
            product_id="Prod_1",
            defaults={"name": "BetaTrax Demo Product", "owner_id": "owner-001"},
        )
        fields_to_update = []
        if product.owner_id != "owner-001":
            product.owner_id = "owner-001"
            fields_to_update.append("owner_id")
        if product.name != "BetaTrax Demo Product":
            product.name = "BetaTrax Demo Product"
            fields_to_update.append("name")
        if fields_to_update:
            product.save(update_fields=fields_to_update)

        ProductDeveloper.objects.get_or_create(product=product, developer_id="dev-001")
        DefectReport.objects.get_or_create(
            report_id="BT-RP-1002",
            defaults={
                "product": product,
                "version": "0.9.0",
                "title": "Poor readability in dark mode",
                "description": "Text unclear in dark mode due to lack of contrast with background",
                "steps": "1. Enable dark mode\n2. Display text",
                "tester_id": "Tester_2",
                "status": DefectStatus.NEW,
            },
        )

    def test_submit_defect_missing_required_fields_returns_400(self):
        response = self.client.post(
            self.create_url,
            data=json.dumps({"product_id": "Prod_1"}),
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
            "product_id": "Prod_1",
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
        action_url = reverse("defects:api-defect-action", kwargs={"defect_id": "BT-RP-1002"})
        self.client.force_login(self.owner_user)
        accept_response = self.client.post(
            action_url,
            data=json.dumps({"action": "accept_open", "severity": "High", "priority": "P1"}),
            content_type="application/json",
        )
        self.assertEqual(accept_response.status_code, 200)

        self.client.force_login(self.dev_user)
        response = self.client.get(self.list_url, {"status": "Open", "developer_id": "dev-001"})
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertTrue(any(item["status"] == DefectStatus.OPEN for item in items))

    def test_owner_can_get_defect_detail(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(self.detail_url("BT-RP-1002"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["report_id"], "BT-RP-1002")
        self.assertIn("description", body)
        self.assertIn("steps", body)

    def test_developer_cannot_get_new_defect_detail(self):
        self.client.force_login(self.dev_user)
        response = self.client.get(self.detail_url("BT-RP-1002"))
        self.assertEqual(response.status_code, 403)
        self.assertIn("cannot access New", response.json()["error"])

    def test_developer_cannot_list_new(self):
        self.client.force_login(self.dev_user)
        response = self.client.get(self.list_url, {"status": "New"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("cannot access New", response.json()["error"])

    def test_take_ownership_requires_team_membership(self):
        accept_url = reverse("defects:api-defect-action", kwargs={"defect_id": "BT-RP-1002"})
        self.client.force_login(self.owner_user)
        accept_response = self.client.post(
            accept_url,
            data=json.dumps({"action": "accept_open", "severity": "High", "priority": "P1"}),
            content_type="application/json",
        )
        self.assertEqual(accept_response.status_code, 200)

        user_model = get_user_model()
        outsider = user_model.objects.create_user(username="dev-999", password="Pass1234!")
        outsider.groups.add(Group.objects.get(name="developer"))
        self.client.force_login(outsider)
        action_url = reverse("defects:api-defect-action", kwargs={"defect_id": "BT-RP-1002"})
        response = self.client.post(
            action_url,
            data=json.dumps({"action": "take_ownership"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("product team", response.json()["error"])

    def test_lifecycle_open_to_assigned_to_fixed_to_resolved(self):
        action_url = reverse("defects:api-defect-action", kwargs={"defect_id": "BT-RP-1002"})
        self.client.force_login(self.owner_user)
        response = self.client.post(
            action_url,
            data=json.dumps({"action": "accept_open", "severity": "High", "priority": "P1"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.OPEN)

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

    def test_product_owner_can_register_product(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user(username="owner-002", password="Pass1234!")
        owner.groups.add(self.owner_group)
        new_dev = user_model.objects.create_user(username="dev-777", password="Pass1234!")
        new_dev.groups.add(self.developer_group)

        self.client.force_login(owner)
        response = self.client.post(
            self.register_url,
            data=json.dumps(
                {
                    "product_id": "Prod_2",
                    "name": "New Product",
                    "developers": ["dev-777"],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Product.objects.filter(product_id="Prod_2", owner_id="owner-002").exists())
        self.assertTrue(ProductDeveloper.objects.filter(product_id="Prod_2", developer_id="dev-777").exists())

    def test_owner_with_existing_product_cannot_register_again(self):
        self.client.force_login(self.owner_user)
        response = self.client.post(
            self.register_url,
            data=json.dumps({"product_id": "Prod_3", "name": "Another Product", "developers": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("已经注册过一个产品", response.json()["error"])

    def test_developer_cannot_register_product(self):
        self.client.force_login(self.dev_user)
        response = self.client.post(
            self.register_url,
            data=json.dumps({"product_id": "Prod_4", "name": "Forbidden Product", "developers": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_owner_can_reject_new_defect(self):
        create_response = self.client.post(
            self.create_url,
            data=json.dumps(
                {
                    "product_id": "Prod_1",
                    "version": "1.0.0",
                    "title": "reject-flow",
                    "description": "desc",
                    "steps": "steps",
                    "tester_id": "tester-r",
                }
            ),
            content_type="application/json",
        )
        defect_id = create_response.json()["report_id"]

        self.client.force_login(self.owner_user)
        action_url = reverse("defects:api-defect-action", kwargs={"defect_id": defect_id})
        response = self.client.post(
            action_url,
            data=json.dumps({"action": "reject"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.REJECTED)

    def test_owner_can_mark_duplicate_with_reference(self):
        target_response = self.client.post(
            self.create_url,
            data=json.dumps(
                {
                    "product_id": "Prod_1",
                    "version": "1.0.0",
                    "title": "target-defect",
                    "description": "desc",
                    "steps": "steps",
                    "tester_id": "tester-t",
                }
            ),
            content_type="application/json",
        )
        duplicate_response = self.client.post(
            self.create_url,
            data=json.dumps(
                {
                    "product_id": "Prod_1",
                    "version": "1.0.0",
                    "title": "duplicate-defect",
                    "description": "desc",
                    "steps": "steps",
                    "tester_id": "tester-d",
                }
            ),
            content_type="application/json",
        )
        target_id = target_response.json()["report_id"]
        duplicate_id = duplicate_response.json()["report_id"]

        self.client.force_login(self.owner_user)
        action_url = reverse("defects:api-defect-action", kwargs={"defect_id": duplicate_id})
        response = self.client.post(
            action_url,
            data=json.dumps({"action": "duplicate", "duplicate_of": target_id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.DUPLICATE)

        defect = DefectReport.objects.get(report_id=duplicate_id)
        self.assertIsNotNone(defect.duplicate_of)
        self.assertEqual(defect.duplicate_of.report_id, target_id)

    def test_duplicate_requires_existing_target(self):
        create_response = self.client.post(
            self.create_url,
            data=json.dumps(
                {
                    "product_id": "Prod_1",
                    "version": "1.0.0",
                    "title": "duplicate-invalid-target",
                    "description": "desc",
                    "steps": "steps",
                    "tester_id": "tester-x",
                }
            ),
            content_type="application/json",
        )
        defect_id = create_response.json()["report_id"]

        self.client.force_login(self.owner_user)
        action_url = reverse("defects:api-defect-action", kwargs={"defect_id": defect_id})
        response = self.client.post(
            action_url,
            data=json.dumps({"action": "duplicate", "duplicate_of": "BT-RP-999999"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Duplicate target report does not exist", response.json()["error"])

    def test_assigned_developer_can_mark_cannot_reproduce(self):
        create_response = self.client.post(
            self.create_url,
            data=json.dumps(
                {
                    "product_id": "Prod_1",
                    "version": "1.0.0",
                    "title": "cannot-reproduce-flow",
                    "description": "desc",
                    "steps": "steps",
                    "tester_id": "tester-c",
                }
            ),
            content_type="application/json",
        )
        defect_id = create_response.json()["report_id"]
        action_url = reverse("defects:api-defect-action", kwargs={"defect_id": defect_id})

        self.client.force_login(self.owner_user)
        self.client.post(
            action_url,
            data=json.dumps({"action": "accept_open", "severity": "High", "priority": "P1"}),
            content_type="application/json",
        )

        self.client.force_login(self.dev_user)
        self.client.post(
            action_url,
            data=json.dumps({"action": "take_ownership"}),
            content_type="application/json",
        )
        response = self.client.post(
            action_url,
            data=json.dumps({"action": "cannot_reproduce", "fix_note": "cannot repro locally"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.CANNOT_REPRODUCE)

    def test_owner_can_reopen_fixed_defect(self):
        create_response = self.client.post(
            self.create_url,
            data=json.dumps(
                {
                    "product_id": "Prod_1",
                    "version": "1.0.0",
                    "title": "reopen-flow",
                    "description": "desc",
                    "steps": "steps",
                    "tester_id": "tester-o",
                }
            ),
            content_type="application/json",
        )
        defect_id = create_response.json()["report_id"]
        action_url = reverse("defects:api-defect-action", kwargs={"defect_id": defect_id})

        self.client.force_login(self.owner_user)
        self.client.post(
            action_url,
            data=json.dumps({"action": "accept_open", "severity": "High", "priority": "P1"}),
            content_type="application/json",
        )

        self.client.force_login(self.dev_user)
        self.client.post(
            action_url,
            data=json.dumps({"action": "take_ownership"}),
            content_type="application/json",
        )
        self.client.post(
            action_url,
            data=json.dumps({"action": "set_fixed", "fix_note": "patched"}),
            content_type="application/json",
        )

        self.client.force_login(self.owner_user)
        response = self.client.post(
            action_url,
            data=json.dumps({"action": "reopen", "retest_note": "still failing"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.REOPENED)

    def test_owner_can_add_comment_and_empty_comment_is_rejected(self):
        self.client.force_login(self.owner_user)
        action_url = reverse("defects:api-defect-action", kwargs={"defect_id": "BT-RP-1002"})

        ok_response = self.client.post(
            action_url,
            data=json.dumps({"action": "add_comment", "comment": "Need more repro info"}),
            content_type="application/json",
        )
        self.assertEqual(ok_response.status_code, 200)
        self.assertEqual(ok_response.json()["message"], "Comment added.")
        self.assertTrue(
            DefectComment.objects.filter(defect_id="BT-RP-1002", author_id="owner-001", text="Need more repro info").exists()
        )

        bad_response = self.client.post(
            action_url,
            data=json.dumps({"action": "add_comment", "comment": "   "}),
            content_type="application/json",
        )
        self.assertEqual(bad_response.status_code, 400)
        self.assertIn("Comment text is required", bad_response.json()["error"])

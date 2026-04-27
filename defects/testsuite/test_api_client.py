from django.conf import settings
from unittest import skipIf

from defects.models import DefectComment, DefectReport, DefectStatus, Product, ProductDeveloper

from .base import DefectApiTestCase


@skipIf(settings.USE_DJANGO_TENANTS, "Single-schema API regression tests run with ENABLE_DJANGO_TENANTS=False.")
class DefectApiClientTests(DefectApiTestCase):
    def test_submit_defect_invalid_email_returns_serializer_error(self):
        response = self.api_post(
            self.create_url,
            {
                "product_id": self.product.product_id,
                "version": "v1",
                "title": "Bad email",
                "description": "desc",
                "steps": "steps",
                "tester_id": "tester-001",
                "email": "not-an-email",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json()["error"])

    def test_submit_defect_missing_required_fields_returns_400(self):
        response = self.api_post(self.create_url, {"product_id": self.product.product_id})
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
        response = self.api_post(self.create_url, payload)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "Unknown Product ID.")

    def test_submit_defect_success_stored_as_new(self):
        response, report_id = self.create_defect()
        self.assertEqual(response.status_code, 201)
        defect = DefectReport.objects.get(report_id=report_id)
        self.assertEqual(defect.status, DefectStatus.NEW)
        self.assertEqual(defect.tester_email, "")

    def test_list_requires_authentication(self):
        response = self.api_get(self.list_url, params={"status": "Open"})
        self.assertEqual(response.status_code, 403)

    def test_list_open_defects_for_developer(self):
        accept_response = self.move_defect_to_open()
        self.assertEqual(accept_response.status_code, 200)

        response = self.api_get(
            self.list_url,
            user=self.dev_user,
            params={"status": "Open"},
        )
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertTrue(any(item["status"] == DefectStatus.OPEN for item in items))

    def test_list_rejects_authenticated_user_without_role(self):
        outsider = self.create_user("viewer-001", "viewer@example.com")
        response = self.api_get(self.list_url, user=outsider)
        self.assertEqual(response.status_code, 403)
        self.assertIn("Only Product Owner or Developer", response.json()["error"])

    def test_list_uses_authenticated_scope_without_owner_or_developer_filters(self):
        self.seed_defect.status = DefectStatus.OPEN
        self.seed_defect.save(update_fields=["status"])

        owner_response = self.api_get(
            self.list_url,
            user=self.owner_user,
        )
        self.assertEqual(owner_response.status_code, 200)
        self.assertEqual(len(owner_response.json()["items"]), 1)

        developer_response = self.api_get(
            self.list_url,
            user=self.dev_user,
        )
        self.assertEqual(developer_response.status_code, 200)
        self.assertEqual(len(developer_response.json()["items"]), 1)

    def test_owner_can_filter_list_by_product(self):
        other_owner = self.create_user("owner-002", "owner002@example.com", self.owner_group)
        other_product = Product.objects.create(product_id="Prod_2", name="Other", owner_id=other_owner.username)
        DefectReport.objects.create(
            report_id="BT-RP-2000",
            product=other_product,
            version="1.0.0",
            title="Other owner defect",
            description="desc",
            steps="steps",
            tester_id="tester-z",
            status=DefectStatus.NEW,
        )
        response = self.api_get(
            self.list_url,
            user=self.owner_user,
            params={"product_id": self.product.product_id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 1)

    def test_owner_can_get_defect_detail(self):
        response = self.api_get(self.detail_url(self.seed_defect.report_id), user=self.owner_user)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["report_id"], self.seed_defect.report_id)
        self.assertIn("description", body)
        self.assertIn("steps", body)

    def test_developer_cannot_get_new_defect_detail(self):
        response = self.api_get(self.detail_url(self.seed_defect.report_id), user=self.dev_user)
        self.assertEqual(response.status_code, 403)
        self.assertIn("cannot access New", response.json()["error"])

    def test_detail_returns_404_for_unknown_or_out_of_scope_defect(self):
        not_found = self.api_get(self.detail_url("BT-RP-9999"), user=self.owner_user)
        self.assertEqual(not_found.status_code, 404)

        other_owner = self.create_user("owner-003", "owner003@example.com", self.owner_group)
        other_product = Product.objects.create(product_id="Prod_3", name="Third", owner_id=other_owner.username)
        other_defect = DefectReport.objects.create(
            report_id="BT-RP-3000",
            product=other_product,
            version="1.0.0",
            title="Scoped defect",
            description="desc",
            steps="steps",
            tester_id="tester-y",
            status=DefectStatus.OPEN,
        )
        out_of_scope = self.api_get(self.detail_url(other_defect.report_id), user=self.owner_user)
        self.assertEqual(out_of_scope.status_code, 404)

    def test_developer_without_team_membership_cannot_get_detail(self):
        outsider = self.create_user("dev-404", "dev404@example.com", self.developer_group)
        self.seed_defect.status = DefectStatus.OPEN
        self.seed_defect.save(update_fields=["status"])
        response = self.api_get(self.detail_url(self.seed_defect.report_id), user=outsider)
        self.assertEqual(response.status_code, 404)

    def test_developer_can_get_open_defect_detail_for_assigned_product(self):
        self.seed_defect.status = DefectStatus.OPEN
        self.seed_defect.save(update_fields=["status"])
        response = self.api_get(self.detail_url(self.seed_defect.report_id), user=self.dev_user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["report_id"], self.seed_defect.report_id)

    def test_developer_cannot_list_new(self):
        response = self.api_get(self.list_url, user=self.dev_user, params={"status": "New"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("cannot access New", response.json()["error"])

    def test_take_ownership_requires_team_membership(self):
        accept_response = self.move_defect_to_open()
        self.assertEqual(accept_response.status_code, 200)

        outsider = self.create_user("dev-999", "dev999@example.com", self.developer_group)
        response = self.api_post(self.action_url(self.seed_defect.report_id), {"action": "take_ownership"}, user=outsider)
        self.assertEqual(response.status_code, 400)
        self.assertIn("product team", response.json()["error"])

    def test_lifecycle_open_to_assigned_to_fixed_to_resolved(self):
        response = self.move_defect_to_open()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.OPEN)

        response = self.api_post(self.action_url(self.seed_defect.report_id), {"action": "take_ownership"}, user=self.dev_user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.ASSIGNED)

        response = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"action": "set_fixed", "fix_note": "patched"},
            user=self.dev_user,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.FIXED)

        response = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"action": "set_resolved", "retest_note": "verified"},
            user=self.owner_user,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.RESOLVED)

    def test_product_owner_can_register_product(self):
        owner = self.create_user("owner-002", "owner002@example.com", self.owner_group)
        new_dev = self.create_user("dev-777", "dev777@example.com", self.developer_group)

        response = self.api_post(
            self.register_url,
            {
                "product_id": "Prod_2",
                "name": "New Product",
                "developers": [new_dev.username],
            },
            user=owner,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Product.objects.filter(product_id="Prod_2", owner_id=owner.username).exists())
        self.assertTrue(ProductDeveloper.objects.filter(product_id="Prod_2", developer_id=new_dev.username).exists())

    def test_owner_with_existing_product_cannot_register_again(self):
        response = self.api_post(
            self.register_url,
            {"product_id": "Prod_3", "name": "Another Product", "developers": []},
            user=self.owner_user,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("already registered a product", response.json()["error"])

    def test_developer_cannot_register_product(self):
        response = self.api_post(
            self.register_url,
            {"product_id": "Prod_4", "name": "Forbidden Product", "developers": []},
            user=self.dev_user,
        )
        self.assertEqual(response.status_code, 403)

    def test_register_product_returns_validation_error_detail(self):
        owner = self.create_user("owner-004", "owner004@example.com", self.owner_group)
        response = self.api_post(
            self.register_url,
            {"product_id": "Prod_5", "name": "Invalid Developers", "developers": "dev-001"},
            user=owner,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("developers must be an array", response.json()["error"])

    def test_owner_can_reject_new_defect(self):
        create_response, defect_id = self.create_defect(title="reject-flow", tester_id="tester-r")
        self.assertEqual(create_response.status_code, 201)

        response = self.api_post(self.action_url(defect_id), {"action": "reject"}, user=self.owner_user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.REJECTED)

    def test_owner_can_mark_duplicate_with_reference(self):
        _, target_id = self.create_defect(title="target-defect", tester_id="tester-t")
        _, duplicate_id = self.create_defect(title="duplicate-defect", tester_id="tester-d")

        response = self.api_post(
            self.action_url(duplicate_id),
            {"action": "duplicate", "duplicate_of": target_id},
            user=self.owner_user,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.DUPLICATE)

        defect = DefectReport.objects.get(report_id=duplicate_id)
        self.assertIsNotNone(defect.duplicate_of)
        self.assertEqual(defect.duplicate_of.report_id, target_id)

    def test_duplicate_requires_existing_target(self):
        _, defect_id = self.create_defect(title="duplicate-invalid-target", tester_id="tester-x")
        response = self.api_post(
            self.action_url(defect_id),
            {"action": "duplicate", "duplicate_of": "BT-RP-999999"},
            user=self.owner_user,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Duplicate target report does not exist", response.json()["error"])

    def test_assigned_developer_can_mark_cannot_reproduce(self):
        _, defect_id = self.create_defect(title="cannot-reproduce-flow", tester_id="tester-c")
        self.move_defect_to_assigned(defect_id)

        response = self.api_post(
            self.action_url(defect_id),
            {"action": "cannot_reproduce", "fix_note": "cannot repro locally"},
            user=self.dev_user,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.CANNOT_REPRODUCE)

    def test_owner_can_reopen_fixed_defect(self):
        _, defect_id = self.create_defect(title="reopen-flow", tester_id="tester-o")
        self.move_defect_to_fixed(defect_id)

        response = self.api_post(
            self.action_url(defect_id),
            {"action": "reopen", "retest_note": "still failing"},
            user=self.owner_user,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.REOPENED)

    def test_owner_can_add_comment_and_empty_comment_is_rejected(self):
        ok_response = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"action": "add_comment", "comment": "Need more repro info"},
            user=self.owner_user,
        )
        self.assertEqual(ok_response.status_code, 200)
        self.assertEqual(ok_response.json()["message"], "Comment added.")
        self.assertTrue(
            DefectComment.objects.filter(
                defect_id=self.seed_defect.report_id,
                author_id=self.owner_user.username,
                text="Need more repro info",
            ).exists()
        )

        bad_response = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"action": "add_comment", "comment": "   "},
            user=self.owner_user,
        )
        self.assertEqual(bad_response.status_code, 400)
        self.assertIn("Comment text is required", bad_response.json()["error"])

    def test_action_returns_404_and_serializer_errors(self):
        missing_defect = self.api_post(
            self.action_url("BT-RP-9999"),
            {"action": "reject"},
            user=self.owner_user,
        )
        self.assertEqual(missing_defect.status_code, 404)

        missing_action = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"comment": "missing action"},
            user=self.owner_user,
        )
        self.assertEqual(missing_action.status_code, 400)
        self.assertIn("action", missing_action.json()["error"])

    def test_platform_admin_can_register_tenant(self):
        admin_user = self.create_user("platform-admin", "platform-admin@example.com")
        admin_user.is_superuser = True
        admin_user.is_staff = True
        admin_user.save(update_fields=["is_superuser", "is_staff"])

        response = self.api_post(
            self.tenant_register_url,
            {
                "schema_name": "team_blue",
                "domain": "team-blue.example.com",
                "name": "Team Blue",
            },
            user=admin_user,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["tenant"]["schema_name"], "team_blue")

        duplicate = self.api_post(
            self.tenant_register_url,
            {
                "schema_name": "team_blue",
                "domain": "team-blue-2.example.com",
                "name": "Team Blue Clone",
            },
            user=admin_user,
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("schema_name already exists", duplicate.json()["error"])

    def test_platform_admin_register_tenant_requires_serializer_fields(self):
        admin_user = self.create_user("platform-admin-2", "platform-admin-2@example.com")
        admin_user.is_superuser = True
        admin_user.is_staff = True
        admin_user.save(update_fields=["is_superuser", "is_staff"])

        response = self.api_post(
            self.tenant_register_url,
            {
                "domain": "missing-schema.example.com",
            },
            user=admin_user,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("schema_name", response.json()["error"])

    def test_non_platform_admin_cannot_register_tenant(self):
        response = self.api_post(
            self.tenant_register_url,
            {
                "schema_name": "team_green",
                "domain": "team-green.example.com",
            },
            user=self.owner_user,
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("platform admins", response.json()["error"])

    def test_product_owner_can_query_developer_effectiveness(self):
        _, defect_id = self.create_defect(title="effectiveness-endpoint", tester_id="tester-effect")
        self.move_defect_to_fixed(defect_id)

        response = self.api_get(
            self.developer_effectiveness_url(self.dev_user.username),
            user=self.owner_user,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["developer_id"], self.dev_user.username)
        self.assertEqual(body["fixed"], 1)
        self.assertEqual(body["reopened"], 0)
        self.assertEqual(body["classification"], "Insufficient data")

    def test_developer_cannot_query_effectiveness(self):
        response = self.api_get(
            self.developer_effectiveness_url(self.dev_user.username),
            user=self.dev_user,
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("product owners", response.json()["error"])

    def test_effectiveness_rejects_non_team_developer(self):
        response = self.api_get(
            self.developer_effectiveness_url("dev-999"),
            user=self.owner_user,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("not in the current product owner's team", response.json()["error"])

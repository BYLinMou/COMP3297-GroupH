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
            params={"status": "Open", "developer_id": self.dev_user.username},
        )
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertTrue(any(item["status"] == DefectStatus.OPEN for item in items))

    def test_owner_can_filter_list_by_slug_and_spaced_status_values(self):
        _, defect_id = self.create_defect(title="cannot-repro-filter", tester_id="tester-filter")
        self.move_defect_to_assigned(defect_id)
        cannot_repro_response = self.api_post(
            self.action_url(defect_id),
            {"action": "cannot_reproduce", "fix_note": "cannot repro in qa"},
            user=self.dev_user,
        )
        self.assertEqual(cannot_repro_response.status_code, 200)

        slug_response = self.api_get(
            self.list_url,
            user=self.owner_user,
            params={"status": "cannot-reproduce"},
        )
        self.assertEqual(slug_response.status_code, 200)
        self.assertTrue(any(item["report_id"] == defect_id for item in slug_response.json()["items"]))

        spaced_response = self.api_get(
            self.list_url,
            user=self.owner_user,
            params={"status": "Cannot Reproduce"},
        )
        self.assertEqual(spaced_response.status_code, 200)
        self.assertTrue(any(item["report_id"] == defect_id for item in spaced_response.json()["items"]))

    def test_developer_can_filter_reopened_with_slug_status_value(self):
        _, defect_id = self.create_defect(title="reopened-filter", tester_id="tester-reopen-filter")
        self.move_defect_to_fixed(defect_id)
        reopen_response = self.api_post(
            self.action_url(defect_id),
            {"action": "reopen", "retest_note": "still broken in prod"},
            user=self.owner_user,
        )
        self.assertEqual(reopen_response.status_code, 200)

        response = self.api_get(
            self.list_url,
            user=self.dev_user,
            params={"status": "reopened", "developer_id": self.dev_user.username},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(item["report_id"] == defect_id for item in response.json()["items"]))

    def test_list_rejects_authenticated_user_without_role(self):
        outsider = self.create_user("viewer-001", "viewer@example.com")
        response = self.api_get(self.list_url, user=outsider)
        self.assertEqual(response.status_code, 403)
        self.assertIn("Only Product Owner or Developer", response.json()["error"])

    def test_list_enforces_owner_and_developer_query_scope(self):
        owner_scope_response = self.api_get(
            self.list_url,
            user=self.owner_user,
            params={"owner_id": "owner-999"},
        )
        self.assertEqual(owner_scope_response.status_code, 403)
        self.assertIn("owner_id must match", owner_scope_response.json()["error"])

        developer_scope_response = self.api_get(
            self.list_url,
            user=self.dev_user,
            params={"developer_id": "dev-999"},
        )
        self.assertEqual(developer_scope_response.status_code, 403)
        self.assertIn("developer_id must match", developer_scope_response.json()["error"])

    def test_list_allows_matching_owner_and_developer_scope_filters(self):
        self.seed_defect.status = DefectStatus.OPEN
        self.seed_defect.save(update_fields=["status"])

        owner_response = self.api_get(
            self.list_url,
            user=self.owner_user,
            params={"owner_id": self.owner_user.username},
        )
        self.assertEqual(owner_response.status_code, 200)
        self.assertEqual(len(owner_response.json()["items"]), 1)

        developer_response = self.api_get(
            self.list_url,
            user=self.dev_user,
            params={"developer_id": self.dev_user.username},
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

    def test_register_product_rejects_blank_fields_and_unknown_or_assigned_developers(self):
        owner = self.create_user("owner-005", "owner005@example.com", self.owner_group)

        blank_product_id = self.api_post(
            self.register_url,
            {"product_id": "", "name": "Blank Product", "developers": []},
            user=owner,
        )
        self.assertEqual(blank_product_id.status_code, 400)
        self.assertIn("product_id cannot be empty", blank_product_id.json()["error"])

        blank_name = self.api_post(
            self.register_url,
            {"product_id": "Prod_20", "name": "", "developers": []},
            user=owner,
        )
        self.assertEqual(blank_name.status_code, 400)
        self.assertIn("name cannot be empty", blank_name.json()["error"])

        blank_developer = self.api_post(
            self.register_url,
            {"product_id": "Prod_21", "name": "Bad Developer", "developers": ["   "]},
            user=owner,
        )
        self.assertEqual(blank_developer.status_code, 400)
        self.assertIn("Developer ID cannot be empty", blank_developer.json()["error"])

        missing_developer = self.api_post(
            self.register_url,
            {"product_id": "Prod_22", "name": "Unknown Developer", "developers": ["missing-dev"]},
            user=owner,
        )
        self.assertEqual(missing_developer.status_code, 400)
        self.assertIn("was not found", missing_developer.json()["error"])

        assigned_developer = self.api_post(
            self.register_url,
            {"product_id": "Prod_23", "name": "Duplicate Assignment", "developers": [self.dev_user.username]},
            user=owner,
        )
        self.assertEqual(assigned_developer.status_code, 400)
        self.assertIn("already assigned to another product", assigned_developer.json()["error"])

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

    def test_owner_can_mark_duplicate_with_blank_reference(self):
        _, defect_id = self.create_defect(title="duplicate-blank-target", tester_id="tester-b")
        response = self.api_post(
            self.action_url(defect_id),
            {"action": "duplicate", "duplicate_of": ""},
            user=self.owner_user,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DefectStatus.DUPLICATE)
        defect = DefectReport.objects.get(report_id=defect_id)
        self.assertIsNone(defect.duplicate_of)

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

    def test_action_endpoint_rejects_invalid_actor_or_state_transitions(self):
        developer_reject = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"action": "reject"},
            user=self.dev_user,
        )
        self.assertEqual(developer_reject.status_code, 400)
        self.assertIn("Only Product Owner role can reject", developer_reject.json()["error"])

        open_response = self.move_defect_to_open()
        self.assertEqual(open_response.status_code, 200)

        resolve_before_fixed = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"action": "set_resolved", "retest_note": "verified"},
            user=self.owner_user,
        )
        self.assertEqual(resolve_before_fixed.status_code, 400)
        self.assertIn("Only Fixed defects can be resolved", resolve_before_fixed.json()["error"])

        assigned_response = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"action": "take_ownership"},
            user=self.dev_user,
        )
        self.assertEqual(assigned_response.status_code, 200)

        other_dev = self.create_user("dev-002", "dev002@example.com", self.developer_group)
        ProductDeveloper.objects.get_or_create(product=self.product, developer_id=other_dev.username)
        wrong_developer_fixed = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"action": "set_fixed", "fix_note": "attempt by wrong developer"},
            user=other_dev,
        )
        self.assertEqual(wrong_developer_fixed.status_code, 400)
        self.assertIn("Only the assigned developer", wrong_developer_fixed.json()["error"])

    def test_action_endpoint_rejects_invalid_accept_fixed_reopen_and_cannot_reproduce_payloads(self):
        invalid_severity = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"action": "accept_open", "severity": "Critical", "priority": "P1"},
            user=self.owner_user,
        )
        self.assertEqual(invalid_severity.status_code, 400)
        self.assertIn("Severity must be High, Medium, or Low", invalid_severity.json()["error"])

        invalid_priority = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"action": "accept_open", "severity": "High", "priority": "P9"},
            user=self.owner_user,
        )
        self.assertEqual(invalid_priority.status_code, 400)
        self.assertIn("Priority must be P1, P2, or P3", invalid_priority.json()["error"])

        open_response = self.move_defect_to_open()
        self.assertEqual(open_response.status_code, 200)
        assigned_response = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"action": "take_ownership"},
            user=self.dev_user,
        )
        self.assertEqual(assigned_response.status_code, 200)

        owner_fixed = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"action": "set_fixed", "fix_note": "owner should fail"},
            user=self.owner_user,
        )
        self.assertEqual(owner_fixed.status_code, 400)
        self.assertIn("Only Developer role can set defect to Fixed", owner_fixed.json()["error"])

        other_dev = self.create_user("dev-003", "dev003@example.com", self.developer_group)
        ProductDeveloper.objects.get_or_create(product=self.product, developer_id=other_dev.username)
        wrong_dev_cannot_repro = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"action": "cannot_reproduce", "fix_note": "wrong dev cannot repro"},
            user=other_dev,
        )
        self.assertEqual(wrong_dev_cannot_repro.status_code, 400)
        self.assertIn(
            "Only the assigned developer may mark this defect Cannot Reproduce",
            wrong_dev_cannot_repro.json()["error"],
        )

        fixed_response = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"action": "set_fixed", "fix_note": "patched by assignee"},
            user=self.dev_user,
        )
        self.assertEqual(fixed_response.status_code, 200)

        other_owner = self.create_user("owner-006", "owner006@example.com", self.owner_group)
        wrong_owner_reopen = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"action": "reopen", "retest_note": "wrong owner reopen"},
            user=other_owner,
        )
        self.assertEqual(wrong_owner_reopen.status_code, 400)
        self.assertIn("Only the Product Owner can reopen", wrong_owner_reopen.json()["error"])

    def test_action_endpoint_rejects_duplicate_by_wrong_owner_and_resolve_by_developer(self):
        _, defect_id = self.create_defect(title="wrong-owner-duplicate", tester_id="tester-wrong-owner")
        _, target_id = self.create_defect(title="wrong-owner-target", tester_id="tester-wrong-target")

        other_owner = self.create_user("owner-007", "owner007@example.com", self.owner_group)
        wrong_owner_duplicate = self.api_post(
            self.action_url(defect_id),
            {"action": "duplicate", "duplicate_of": target_id},
            user=other_owner,
        )
        self.assertEqual(wrong_owner_duplicate.status_code, 400)
        self.assertIn("Only the Product Owner can mark duplicate", wrong_owner_duplicate.json()["error"])

        self.move_defect_to_fixed(defect_id)
        developer_resolve = self.api_post(
            self.action_url(defect_id),
            {"action": "set_resolved", "retest_note": "developer should not resolve"},
            user=self.dev_user,
        )
        self.assertEqual(developer_resolve.status_code, 400)
        self.assertIn("Only Product Owner role can resolve", developer_resolve.json()["error"])

    def test_action_endpoint_blocks_cross_product_owner_and_developer_access(self):
        other_owner = self.create_user("owner-008", "owner008@example.com", self.owner_group)
        other_developer = self.create_user("dev-008", "dev008@example.com", self.developer_group)
        other_product = Product.objects.create(product_id="Prod_8", name="Cross Scope", owner_id=other_owner.username)
        ProductDeveloper.objects.create(product=other_product, developer_id=other_developer.username)
        other_defect = DefectReport.objects.create(
            report_id="BT-RP-8000",
            product=other_product,
            version="2.0.0",
            title="Cross product defect",
            description="desc",
            steps="steps",
            tester_id="tester-cross",
            status=DefectStatus.NEW,
        )

        wrong_owner_reject = self.api_post(
            self.action_url(other_defect.report_id),
            {"action": "reject"},
            user=self.owner_user,
        )
        self.assertEqual(wrong_owner_reject.status_code, 400)
        self.assertIn("Only the Product Owner can reject", wrong_owner_reject.json()["error"])

        other_defect.status = DefectStatus.OPEN
        other_defect.save(update_fields=["status"])
        wrong_developer_take = self.api_post(
            self.action_url(other_defect.report_id),
            {"action": "take_ownership"},
            user=self.dev_user,
        )
        self.assertEqual(wrong_developer_take.status_code, 400)
        self.assertIn("Only developers on the product team", wrong_developer_take.json()["error"])

    def test_list_with_unknown_status_returns_empty_result_for_owner(self):
        response = self.api_get(
            self.list_url,
            user=self.owner_user,
            params={"status": "not-a-real-status"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])

    def test_developer_list_with_unknown_status_returns_empty_result(self):
        self.move_defect_to_open()
        response = self.api_get(
            self.list_url,
            user=self.dev_user,
            params={"status": "not-a-real-status", "developer_id": self.dev_user.username},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])

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

        blank_action = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"action": ""},
            user=self.owner_user,
        )
        self.assertEqual(blank_action.status_code, 400)
        self.assertIn("action", blank_action.json()["error"])

        too_long_action = self.api_post(
            self.action_url(self.seed_defect.report_id),
            {"action": "x" * 65},
            user=self.owner_user,
        )
        self.assertEqual(too_long_action.status_code, 400)
        self.assertIn("action", too_long_action.json()["error"])

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

    def test_product_owner_can_query_effectiveness_good_fair_and_poor(self):
        def create_owner_developer_product(owner_id, developer_id, product_id):
            owner = self.create_user(owner_id, f"{owner_id}@example.com", self.owner_group)
            developer = self.create_user(developer_id, f"{developer_id}@example.com", self.developer_group)
            product = Product.objects.create(product_id=product_id, name=f"{product_id} Name", owner_id=owner.username)
            ProductDeveloper.objects.create(product=product, developer_id=developer.username)
            return owner, developer, product

        def create_and_fix_defect(owner, developer, product, index, reopen=False):
            response = self.api_post(
                self.create_url,
                {
                    "product_id": product.product_id,
                    "version": "v2.0.0",
                    "title": f"{product.product_id}-defect-{index}",
                    "description": "desc",
                    "steps": "steps",
                    "tester_id": f"tester-{product.product_id}-{index}",
                },
            )
            self.assertEqual(response.status_code, 201)
            defect_id = response.json()["report_id"]

            accept_response = self.api_post(
                self.action_url(defect_id),
                {"action": "accept_open", "severity": "High", "priority": "P1"},
                user=owner,
            )
            self.assertEqual(accept_response.status_code, 200)
            take_response = self.api_post(
                self.action_url(defect_id),
                {"action": "take_ownership"},
                user=developer,
            )
            self.assertEqual(take_response.status_code, 200)
            fixed_response = self.api_post(
                self.action_url(defect_id),
                {"action": "set_fixed", "fix_note": f"fix-{index}"},
                user=developer,
            )
            self.assertEqual(fixed_response.status_code, 200)

            if reopen:
                reopen_response = self.api_post(
                    self.action_url(defect_id),
                    {"action": "reopen", "retest_note": f"reopen-{index}"},
                    user=owner,
                )
                self.assertEqual(reopen_response.status_code, 200)

        good_owner, good_dev, good_product = create_owner_developer_product("owner-good", "dev-good", "Prod_Good")
        for index in range(20):
            create_and_fix_defect(good_owner, good_dev, good_product, f"good-{index}")
        good_response = self.api_get(
            self.developer_effectiveness_url(good_dev.username),
            user=good_owner,
        )
        self.assertEqual(good_response.status_code, 200)
        self.assertEqual(good_response.json()["fixed"], 20)
        self.assertEqual(good_response.json()["reopened"], 0)
        self.assertEqual(good_response.json()["classification"], "Good")

        fair_owner, fair_dev, fair_product = create_owner_developer_product("owner-fair", "dev-fair", "Prod_Fair")
        for index in range(31):
            create_and_fix_defect(fair_owner, fair_dev, fair_product, f"fair-{index}")
        create_and_fix_defect(fair_owner, fair_dev, fair_product, "fair-reopen", reopen=True)
        fair_response = self.api_get(
            self.developer_effectiveness_url(fair_dev.username),
            user=fair_owner,
        )
        self.assertEqual(fair_response.status_code, 200)
        self.assertEqual(fair_response.json()["fixed"], 32)
        self.assertEqual(fair_response.json()["reopened"], 1)
        self.assertEqual(fair_response.json()["reopen_ratio"], 1 / 32)
        self.assertEqual(fair_response.json()["classification"], "Fair")

        poor_owner, poor_dev, poor_product = create_owner_developer_product("owner-poor", "dev-poor", "Prod_Poor")
        for index in range(21):
            create_and_fix_defect(poor_owner, poor_dev, poor_product, f"poor-{index}")
        create_and_fix_defect(poor_owner, poor_dev, poor_product, "poor-reopen-1", reopen=True)
        create_and_fix_defect(poor_owner, poor_dev, poor_product, "poor-reopen-2", reopen=True)
        create_and_fix_defect(poor_owner, poor_dev, poor_product, "poor-reopen-3", reopen=True)
        poor_response = self.api_get(
            self.developer_effectiveness_url(poor_dev.username),
            user=poor_owner,
        )
        self.assertEqual(poor_response.status_code, 200)
        self.assertEqual(poor_response.json()["fixed"], 24)
        self.assertEqual(poor_response.json()["reopened"], 3)
        self.assertEqual(poor_response.json()["reopen_ratio"], 3 / 24)
        self.assertEqual(poor_response.json()["classification"], "Poor")

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

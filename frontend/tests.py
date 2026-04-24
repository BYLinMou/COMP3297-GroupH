from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from defects.authz import ROLE_DEVELOPER, ROLE_OWNER
from defects.models import DefectComment, DefectReport, DefectStatus, Product, ProductDeveloper


class FrontendSmokeTests(TestCase):
    password = "Pass1234!"

    def setUp(self):
        self.owner_group, _ = Group.objects.get_or_create(name=ROLE_OWNER)
        self.developer_group, _ = Group.objects.get_or_create(name=ROLE_DEVELOPER)
        self.owner = self._create_user("owner-001", self.owner_group)
        self.developer = self._create_user("dev-001", self.developer_group)
        self.product = Product.objects.create(product_id="Prod_1", name="Demo", owner_id=self.owner.username)
        ProductDeveloper.objects.create(product=self.product, developer_id=self.developer.username)
        self.defect = DefectReport.objects.create(
            report_id="BT-RP-1002",
            product=self.product,
            version="1.0.0",
            title="Cannot save draft",
            description="desc",
            steps="steps",
            tester_id="tester-001",
            status=DefectStatus.NEW,
        )

    def _create_user(self, username, group):
        user, created = get_user_model().objects.get_or_create(username=username)
        if created:
            user.set_password(self.password)
            user.save(update_fields=["password"])
        user.groups.add(group)
        return user

    def test_login_page_renders(self):
        response = self.client.get(reverse("frontend:external-auth"))
        self.assertEqual(response.status_code, 200)

    def test_external_auth_rejects_invalid_credentials_and_accepts_valid_login(self):
        bad_response = self.client.post(
            reverse("frontend:external-auth"),
            {"username": self.owner.username, "password": "wrong"},
            follow=True,
        )
        self.assertEqual(bad_response.status_code, 200)
        self.assertContains(bad_response, "Invalid username or password.")

        good_response = self.client.post(
            reverse("frontend:external-auth"),
            {"username": self.owner.username, "password": self.password},
        )
        self.assertEqual(good_response.status_code, 302)
        self.assertEqual(good_response.url, reverse("frontend:home"))

    def test_sign_out_clears_session(self):
        self.client.login(username=self.owner.username, password=self.password)
        response = self.client.get(reverse("frontend:sign-out"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("frontend:external-auth"))

    def test_owner_home_page_lists_visible_defects(self):
        self.client.login(username=self.owner.username, password=self.password)
        response = self.client.get(reverse("frontend:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.defect.report_id)

    def test_home_redirects_non_role_user_and_filters_statuses(self):
        viewer = get_user_model().objects.create_user(username="viewer", password=self.password)
        self.client.login(username=viewer.username, password=self.password)
        response = self.client.get(reverse("frontend:home"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("frontend:external-auth"))

        self.client.login(username=self.developer.username, password=self.password)
        self.defect.status = DefectStatus.OPEN
        self.defect.save(update_fields=["status"])
        open_response = self.client.get(reverse("frontend:home"), {"status": "open"})
        self.assertEqual(open_response.status_code, 200)
        self.assertContains(open_response, self.defect.report_id)

        hidden_new_response = self.client.get(reverse("frontend:home"), {"status": "new"})
        self.assertEqual(hidden_new_response.status_code, 200)
        self.assertNotContains(hidden_new_response, self.defect.report_id)

        unknown_status_response = self.client.get(reverse("frontend:home"), {"status": "unknown"})
        self.assertEqual(unknown_status_response.status_code, 200)
        self.assertNotContains(unknown_status_response, self.defect.report_id)

    def test_developer_cannot_open_new_defect_detail_page(self):
        self.client.login(username=self.developer.username, password=self.password)
        response = self.client.get(reverse("frontend:defect-detail", args=[self.defect.report_id]))
        self.assertEqual(response.status_code, 404)

    def test_register_product_page_renders_and_non_owner_is_redirected(self):
        self.client.login(username=self.owner.username, password=self.password)
        response = self.client.get(reverse("frontend:register-product"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Register Product")
        self.assertContains(response, self.developer.username)

        self.client.login(username=self.developer.username, password=self.password)
        redirect_response = self.client.get(reverse("frontend:register-product"))
        self.assertEqual(redirect_response.status_code, 302)
        self.assertEqual(redirect_response.url, reverse("frontend:home"))

    def test_register_product_page_handles_missing_developer_group(self):
        Group.objects.filter(name=ROLE_DEVELOPER).delete()
        self.client.login(username=self.owner.username, password=self.password)
        response = self.client.get(reverse("frontend:register-product"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No developer accounts found.")

    def test_owner_can_register_product_and_invalid_submission_is_redisplayed(self):
        owner2 = self._create_user("owner-002", self.owner_group)
        dev2 = self._create_user("dev-002", self.developer_group)

        self.client.login(username=owner2.username, password=self.password)
        invalid_response = self.client.post(
            reverse("frontend:register-product"),
            {"product_id": "Prod_2", "name": "Demo 2", "developers": ["missing-dev"]},
            follow=True,
        )
        self.assertEqual(invalid_response.status_code, 200)
        self.assertContains(invalid_response, "Developer account missing-dev was not found.")
        self.assertContains(invalid_response, "Prod_2")

        success_response = self.client.post(
            reverse("frontend:register-product"),
            {"product_id": "Prod_2", "name": "Demo 2", "developers": [dev2.username]},
        )
        self.assertEqual(success_response.status_code, 302)
        self.assertEqual(success_response.url, reverse("frontend:home"))
        self.assertTrue(Product.objects.filter(product_id="Prod_2", owner_id=owner2.username).exists())
        self.assertTrue(ProductDeveloper.objects.filter(product_id="Prod_2", developer_id=dev2.username).exists())

    def test_create_defect_page_enforces_role_and_validates_submission(self):
        self.client.login(username=self.developer.username, password=self.password)
        redirect_response = self.client.get(reverse("frontend:create-defect"))
        self.assertEqual(redirect_response.status_code, 302)
        self.assertEqual(redirect_response.url, reverse("frontend:home"))

        self.client.login(username=self.owner.username, password=self.password)
        form_response = self.client.get(reverse("frontend:create-defect"))
        self.assertEqual(form_response.status_code, 200)
        self.assertContains(form_response, "Create New Defect")

        missing_response = self.client.post(
            reverse("frontend:create-defect"),
            {"product_id": self.product.product_id, "version": "1.0.1"},
        )
        self.assertEqual(missing_response.status_code, 302)
        self.assertEqual(missing_response.url, reverse("frontend:create-defect"))

        unknown_product_response = self.client.post(
            reverse("frontend:create-defect"),
            {
                "product_id": "Prod_404",
                "version": "1.0.1",
                "title": "Unknown product",
                "description": "desc",
                "steps": "steps",
                "tester_id": "tester-002",
            },
        )
        self.assertEqual(unknown_product_response.status_code, 302)
        self.assertEqual(unknown_product_response.url, reverse("frontend:create-defect"))

        success_response = self.client.post(
            reverse("frontend:create-defect"),
            {
                "product_id": self.product.product_id,
                "version": "1.0.1",
                "title": "Created from UI",
                "description": "desc",
                "steps": "steps",
                "tester_id": "tester-002",
                "email": "tester2@example.com",
            },
        )
        self.assertEqual(success_response.status_code, 302)
        created = DefectReport.objects.get(title="Created from UI")
        self.assertEqual(success_response.url, reverse("frontend:defect-detail", args=[created.report_id]))

    def test_defect_detail_supports_comments_actions_and_scope_checks(self):
        self.client.login(username=self.owner.username, password=self.password)
        detail_response = self.client.get(reverse("frontend:defect-detail", args=[self.defect.report_id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "No comments yet.")

        comment_response = self.client.post(
            reverse("frontend:defect-detail", args=[self.defect.report_id]),
            {"action": "add_comment", "comment": "Need more detail"},
        )
        self.assertEqual(comment_response.status_code, 302)
        self.assertTrue(
            DefectComment.objects.filter(defect=self.defect, author_id=self.owner.username, text="Need more detail").exists()
        )

        invalid_action_response = self.client.post(
            reverse("frontend:defect-detail", args=[self.defect.report_id]),
            {"action": "set_fixed", "fix_note": "not allowed yet"},
        )
        self.assertEqual(invalid_action_response.status_code, 302)

        owner2 = self._create_user("owner-003", self.owner_group)
        self.client.login(username=owner2.username, password=self.password)
        hidden_response = self.client.get(reverse("frontend:defect-detail", args=[self.defect.report_id]))
        self.assertEqual(hidden_response.status_code, 404)

        viewer = get_user_model().objects.create_user(username="viewer-2", password=self.password)
        self.client.login(username=viewer.username, password=self.password)
        roleless_response = self.client.get(reverse("frontend:defect-detail", args=[self.defect.report_id]))
        self.assertEqual(roleless_response.status_code, 302)
        self.assertEqual(roleless_response.url, reverse("frontend:external-auth"))

    def test_defect_detail_returns_404_for_missing_or_unassigned_developer_scope(self):
        self.client.login(username=self.owner.username, password=self.password)
        missing_response = self.client.get(reverse("frontend:defect-detail", args=["BT-RP-9999"]))
        self.assertEqual(missing_response.status_code, 404)

        outsider = self._create_user("dev-404", self.developer_group)
        self.defect.status = DefectStatus.OPEN
        self.defect.save(update_fields=["status"])
        self.client.login(username=outsider.username, password=self.password)
        hidden_response = self.client.get(reverse("frontend:defect-detail", args=[self.defect.report_id]))
        self.assertEqual(hidden_response.status_code, 404)

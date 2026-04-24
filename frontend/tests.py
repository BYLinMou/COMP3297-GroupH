from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from defects.authz import ROLE_DEVELOPER, ROLE_OWNER
from defects.models import DefectReport, DefectStatus, Product, ProductDeveloper


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

    def test_owner_home_page_lists_visible_defects(self):
        self.client.login(username=self.owner.username, password=self.password)
        response = self.client.get(reverse("frontend:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.defect.report_id)

    def test_developer_cannot_open_new_defect_detail_page(self):
        self.client.login(username=self.developer.username, password=self.password)
        response = self.client.get(reverse("frontend:defect-detail", args=[self.defect.report_id]))
        self.assertEqual(response.status_code, 404)

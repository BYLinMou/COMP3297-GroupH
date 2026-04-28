from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from defects.effectiveness import classify_developer
from defects.models import DefectReport, DefectStatus, Product, ProductDeveloper

User = get_user_model()


class EffectivenessClassificationTests(APITestCase):
    """White-box branch coverage for classify_developer."""

    def test_negative_input_raises(self):
        with self.assertRaises(ValueError):
            classify_developer(-1, 0)

    def test_insufficient_data(self):
        # fixed < 20 branch
        self.assertEqual(classify_developer(10, 0), "Insufficient data")

    def test_good(self):
        # ratio 0/20 = 0 < 1/32 branch
        self.assertEqual(classify_developer(20, 0), "Good")

    def test_fair(self):
        # ratio 1/20 = 0.05, between 1/32 and 1/8 branch
        self.assertEqual(classify_developer(20, 1), "Fair")

    def test_poor(self):
        # ratio 4/20 = 0.2 >= 1/8 branch
        self.assertEqual(classify_developer(20, 4), "Poor")


class EndpointTests(APITestCase):
    """One test per API endpoint method."""

    def setUp(self):
        owner_group, _ = Group.objects.get_or_create(name="owner")
        dev_group, _ = Group.objects.get_or_create(name="developer")
        admin_group, _ = Group.objects.get_or_create(name="platform_admin")

        self.owner = User.objects.create_user("owner1", password="pass")
        self.owner.groups.add(owner_group)

        self.dev = User.objects.create_user("dev1", password="pass")
        self.dev.groups.add(dev_group)

        self.admin = User.objects.create_user("admin1", password="pass")
        self.admin.groups.add(admin_group)

        self.product = Product.objects.create(
            product_id="P1", name="Test Product", owner_id="owner1"
        )
        ProductDeveloper.objects.create(product=self.product, developer_id="dev1")

        self.defect = DefectReport.objects.create(
            report_id="BT-RP-9001",
            product=self.product,
            version="1.0",
            title="Test defect",
            description="Desc",
            steps="Steps",
            tester_id="tester1",
            status=DefectStatus.NEW,
        )

    def test_post_defects_new(self):
        response = self.client.post("/api/defects/new/", {
            "product_id": "P1",
            "version": "1.0",
            "title": "New bug",
            "description": "Bug description",
            "steps": "Reproduce steps",
            "tester_id": "tester1",
        }, format="json")
        self.assertEqual(response.status_code, 201)

    def test_get_defects_list(self):
        self.client.force_login(self.owner)
        response = self.client.get("/api/defects/")
        self.assertEqual(response.status_code, 200)

    def test_get_defects_detail(self):
        self.client.force_login(self.owner)
        response = self.client.get(f"/api/defects/{self.defect.report_id}/")
        self.assertEqual(response.status_code, 200)

    def test_post_defects_actions(self):
        self.client.force_login(self.owner)
        response = self.client.post(f"/api/defects/{self.defect.report_id}/actions/", {
            "action": "accept_open",
            "severity": "High",
            "priority": "P1",
        }, format="json")
        self.assertEqual(response.status_code, 200)

    def test_post_products_register(self):
        owner_group = Group.objects.get(name="owner")
        dev_group = Group.objects.get(name="developer")
        owner2 = User.objects.create_user("owner2", password="pass")
        owner2.groups.add(owner_group)
        dev2 = User.objects.create_user("dev2", password="pass")
        dev2.groups.add(dev_group)

        self.client.force_login(owner2)
        response = self.client.post("/api/products/register/", {
            "product_id": "P2",
            "name": "Another Product",
            "developers": ["dev2"],
        }, format="json")
        self.assertEqual(response.status_code, 201)

    def test_post_tenants_register(self):
        self.client.force_login(self.admin)
        response = self.client.post("/api/tenants/register/", {
            "schema_name": "testtenant",
            "domain": "testtenant.localhost",
            "name": "Test Tenant",
        }, format="json")
        self.assertEqual(response.status_code, 201)

    def test_get_developer_effectiveness(self):
        self.client.force_login(self.owner)
        response = self.client.get("/api/developers/dev1/effectiveness/")
        self.assertEqual(response.status_code, 200)

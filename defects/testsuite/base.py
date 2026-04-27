from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework.test import APITestCase

from defects.authz import ROLE_DEVELOPER, ROLE_OWNER
from defects.models import DefectReport, DefectStatus, Product, ProductDeveloper


class DefectApiTestCase(APITestCase):
    password = "Pass1234!"

    def setUp(self):
        self.create_url = reverse("defects:api-create-defect")
        self.list_url = reverse("defects:api-list-defects")
        self.register_url = reverse("api-product-register-root")
        self.tenant_register_url = reverse("api-tenant-register-root")
        self.owner_group, _ = Group.objects.get_or_create(name=ROLE_OWNER)
        self.developer_group, _ = Group.objects.get_or_create(name=ROLE_DEVELOPER)

        self.owner_user = self.create_user("owner-001", "owner001@example.com", self.owner_group)
        self.dev_user = self.create_user("dev-001", "dev001@example.com", self.developer_group)
        self.product = Product.objects.create(
            product_id="Prod_1",
            name="BetaTrax Demo Product",
            owner_id=self.owner_user.username,
        )
        ProductDeveloper.objects.create(product=self.product, developer_id=self.dev_user.username)
        self.seed_defect = DefectReport.objects.create(
            report_id="BT-RP-1002",
            product=self.product,
            version="0.9.0",
            title="Poor readability in dark mode",
            description="Text unclear in dark mode due to lack of contrast with background",
            steps="1. Enable dark mode\n2. Display text",
            tester_id="Tester_2",
            status=DefectStatus.NEW,
        )

    def create_user(self, username, email, *groups):
        user, created = get_user_model().objects.get_or_create(
            username=username,
            defaults={"email": email},
        )
        if created:
            user.set_password(self.password)
            user.save(update_fields=["password"])
        elif email and user.email != email:
            user.email = email
            user.save(update_fields=["email"])
        for group in groups:
            user.groups.add(group)
        return user

    def detail_url(self, defect_id):
        return reverse("defects:api-defect-detail", kwargs={"defect_id": defect_id})

    def action_url(self, defect_id):
        return reverse("defects:api-defect-action", kwargs={"defect_id": defect_id})

    def developer_effectiveness_url(self, developer_id):
        return reverse("api-developer-effectiveness", kwargs={"developer_id": developer_id})

    def api_post(self, url, payload, user=None):
        if user is None:
            self.client.logout()
        else:
            self.client.force_authenticate(user=user)
        return self.client.post(url, data=payload, format="json")

    def api_get(self, url, user=None, params=None):
        if user is None:
            self.client.logout()
        else:
            self.client.force_authenticate(user=user)
        return self.client.get(url, data=params or {}, format="json")

    def create_defect(self, title="UI glitch", tester_id="tester-009", **overrides):
        payload = {
            "product_id": self.product.product_id,
            "version": "v1.5.0-beta",
            "title": title,
            "description": "visual issue",
            "steps": "1. open page",
            "tester_id": tester_id,
        }
        payload.update(overrides)
        response = self.api_post(self.create_url, payload)
        return response, response.json().get("report_id")

    def move_defect_to_open(self, defect_id="BT-RP-1002", **payload_overrides):
        payload = {"action": "accept_open", "severity": "High", "priority": "P1"}
        payload.update(payload_overrides)
        return self.api_post(self.action_url(defect_id), payload, user=self.owner_user)

    def move_defect_to_assigned(self, defect_id="BT-RP-1002"):
        self.move_defect_to_open(defect_id)
        return self.api_post(self.action_url(defect_id), {"action": "take_ownership"}, user=self.dev_user)

    def move_defect_to_fixed(self, defect_id="BT-RP-1002", fix_note="patched"):
        self.move_defect_to_assigned(defect_id)
        return self.api_post(
            self.action_url(defect_id),
            {"action": "set_fixed", "fix_note": fix_note},
            user=self.dev_user,
        )

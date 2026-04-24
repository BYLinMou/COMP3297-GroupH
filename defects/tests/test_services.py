from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase

from defects.authz import ActorContext
from defects.models import DefectComment, DefectReport, DefectStatus, Product, ProductDeveloper
from defects.services import apply_action, create_defect, next_report_id, register_product


class DefectServiceTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(product_id="Prod_1", name="Demo", owner_id="owner-001")
        ProductDeveloper.objects.create(product=self.product, developer_id="dev-001")
        self.defect = DefectReport.objects.create(
            report_id="BT-RP-2401",
            product=self.product,
            version="1.0.0",
            title="Broken search",
            description="desc",
            steps="steps",
            tester_id="tester-001",
            tester_email="tester@example.com",
            status=DefectStatus.NEW,
        )
        self.owner_actor = ActorContext(actor_id="owner-001", is_owner=True, is_developer=False)
        self.developer_actor = ActorContext(actor_id="dev-001", is_owner=False, is_developer=True)

    def test_create_defect_creates_initial_history_record(self):
        defect = create_defect(
            {
                "product": self.product,
                "version": "1.2.3",
                "title": "Autosave issue",
                "description": "desc",
                "steps": "steps",
                "tester_id": "tester-002",
                "email": "tester2@example.com",
            }
        )
        history = defect.history.get()
        self.assertEqual(history.from_status, DefectStatus.NEW)
        self.assertEqual(history.to_status, DefectStatus.NEW)
        self.assertEqual(history.actor_id, "tester-002")

    def test_next_report_id_skips_invalid_report_identifiers(self):
        DefectReport.objects.create(
            report_id="LEGACY-ID",
            product=self.product,
            version="1.0.0",
            title="Legacy defect",
            description="desc",
            steps="steps",
            tester_id="tester-legacy",
            status=DefectStatus.NEW,
        )
        self.assertEqual(next_report_id(), "BT-RP-2402")

    def test_accept_open_sends_status_email_and_updates_history(self):
        message = apply_action(
            self.defect,
            "accept_open",
            {"severity": "High", "priority": "P1"},
            self.owner_actor,
        )
        self.defect.refresh_from_db()
        self.assertEqual(message, "Defect accepted and moved to Open.")
        self.assertEqual(self.defect.status, DefectStatus.OPEN)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.defect.report_id, mail.outbox[0].subject)
        self.assertEqual(self.defect.history.last().to_status, DefectStatus.OPEN)

    def test_add_comment_persists_comment_record(self):
        message = apply_action(
            self.defect,
            "add_comment",
            {"comment": "Need more logs"},
            self.owner_actor,
        )
        self.assertEqual(message, "Comment added.")
        self.assertTrue(
            DefectComment.objects.filter(defect=self.defect, author_id="owner-001", text="Need more logs").exists()
        )

    def test_register_product_rejects_duplicate_developer_assignment(self):
        owner_user = type("OwnerUser", (), {"username": "owner-002"})()
        with self.assertRaises(ValidationError):
            register_product(
                owner_user=owner_user,
                product_id="Prod_2",
                product_name="Another Demo",
                developer_ids=["dev-001"],
            )

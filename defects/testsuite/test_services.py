from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.exceptions import ValidationError
from django.db.utils import ProgrammingError
from django.test import TestCase, override_settings

from defects.authz import ActorContext, ROLE_DEVELOPER, ROLE_OWNER, actor_from_user
from defects.models import DefectComment, DefectReport, DefectStatus, Product, ProductDeveloper
from defects.services import (
    _demo_dt,
    _iter_duplicate_descendants,
    _record_status_change,
    apply_action,
    create_defect,
    ensure_demo_seed,
    next_report_id,
    register_product,
    summarize_developer_effectiveness,
)
from defects.signals import _defect_tables_ready, _should_seed_demo_data, seed_demo_data
from tenancy.models import Domain, Tenant
from tenancy.services import register_tenant


class DefectSignalTests(TestCase):
    def test_seed_signal_ignores_non_defects_sender(self):
        sender = SimpleNamespace(name="auth")

        self.assertFalse(_should_seed_demo_data(sender))

        with patch("defects.signals.ensure_demo_seed") as mocked_seed:
            seed_demo_data(sender)

        mocked_seed.assert_not_called()

    @override_settings(USE_DJANGO_TENANTS=True)
    def test_seed_signal_skips_public_schema_in_tenant_mode(self):
        sender = SimpleNamespace(name="defects")

        with patch("defects.signals.is_public_schema_context", return_value=True):
            self.assertFalse(_should_seed_demo_data(sender))

            with patch("defects.signals.ensure_demo_seed") as mocked_seed:
                seed_demo_data(sender)

        mocked_seed.assert_not_called()

    @override_settings(USE_DJANGO_TENANTS=False)
    def test_seed_signal_runs_when_defect_tables_exist(self):
        sender = SimpleNamespace(name="defects")

        self.assertTrue(_defect_tables_ready())
        self.assertTrue(_should_seed_demo_data(sender))

        with patch("defects.signals.ensure_demo_seed") as mocked_seed:
            seed_demo_data(sender)

        mocked_seed.assert_called_once_with()

    @override_settings(USE_DJANGO_TENANTS=False)
    def test_seed_signal_skips_when_tables_are_not_ready(self):
        sender = SimpleNamespace(name="defects")

        with patch("defects.signals.connection.introspection.table_names", return_value=[]):
            self.assertFalse(_defect_tables_ready())
            self.assertFalse(_should_seed_demo_data(sender))

        with patch("defects.signals.connection.introspection.table_names", side_effect=ProgrammingError("missing")):
            self.assertFalse(_defect_tables_ready())


class DefectServiceTests(TestCase):
    def setUp(self):
        self.owner_group, _ = Group.objects.get_or_create(name=ROLE_OWNER)
        self.developer_group, _ = Group.objects.get_or_create(name=ROLE_DEVELOPER)
        self.user_model = get_user_model()
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
        self.other_owner_actor = ActorContext(actor_id="owner-999", is_owner=True, is_developer=False)
        self.outsider_actor = ActorContext(actor_id="outsider", is_owner=False, is_developer=False)

    def create_user(self, username, email="", *groups):
        user, created = self.user_model.objects.get_or_create(
            username=username,
            defaults={"email": email or f"{username}@example.com"},
        )
        if created:
            user.set_password("Pass1234!")
            user.save(update_fields=["password"])
        for group in groups:
            user.groups.add(group)
        return user

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

    def test_actor_from_user_handles_anonymous_and_group_membership(self):
        anonymous = actor_from_user(None)
        self.assertEqual(anonymous.actor_id, "")
        self.assertFalse(anonymous.is_owner)
        self.assertFalse(anonymous.is_developer)

        owner = self.create_user("owner-002", "owner2@example.com", self.owner_group)
        actor = actor_from_user(owner)
        self.assertEqual(actor.actor_id, owner.username)
        self.assertTrue(actor.is_owner)
        self.assertFalse(actor.is_developer)

    def test_model_string_representations_are_human_readable(self):
        assignment = ProductDeveloper.objects.get(product=self.product, developer_id="dev-001")
        self.assertEqual(str(self.product), "Prod_1")
        self.assertEqual(str(assignment), "dev-001@Prod_1")
        self.assertEqual(str(self.defect), "BT-RP-2401")

        tenant = Tenant.objects.create(schema_name="tenant_a", domain="tenant-a.example.com")
        self.assertEqual(str(tenant), "tenant_a (tenant-a.example.com)")

    def test_demo_helpers_create_seed_users_and_remove_legacy_records(self):
        legacy_product = Product.objects.create(product_id="PRD-1007", name="Legacy", owner_id="legacy-owner")
        legacy_defect = DefectReport.objects.create(
            report_id="BT-RP-2471",
            product=legacy_product,
            version="0.1.0",
            title="Legacy defect",
            description="desc",
            steps="steps",
            tester_id="tester-old",
            status=DefectStatus.NEW,
        )
        DefectComment.objects.create(defect=legacy_defect, author_id="owner", text="legacy")

        ensure_demo_seed()

        self.assertTrue(self.user_model.objects.filter(username="owner-001", groups__name=ROLE_OWNER).exists())
        self.assertTrue(self.user_model.objects.filter(username="dev-001", groups__name=ROLE_DEVELOPER).exists())
        self.assertTrue(self.user_model.objects.filter(username="dev-004", groups__name=ROLE_DEVELOPER).exists())
        self.assertFalse(Product.objects.filter(product_id="PRD-1007").exists())
        self.assertFalse(DefectReport.objects.filter(report_id="BT-RP-2471").exists())

    def test_demo_helpers_remove_stale_reports_not_linked_to_legacy_product(self):
        stale_defect = DefectReport.objects.create(
            report_id="BT-RP-2476",
            product=self.product,
            version="0.1.1",
            title="Stale defect",
            description="desc",
            steps="steps",
            tester_id="tester-stale",
            status=DefectStatus.NEW,
        )
        DefectComment.objects.create(defect=stale_defect, author_id="owner", text="stale")

        ensure_demo_seed()

        self.assertFalse(DefectReport.objects.filter(report_id="BT-RP-2476").exists())

    def test_demo_dt_supports_iso_strings_with_or_without_timezone(self):
        aware = _demo_dt("2026-04-24T12:30:00+08:00")
        self.assertIsNotNone(aware.tzinfo)
        with patch("defects.services.parse_datetime", return_value=None):
            fallback = _demo_dt("2026-04-24T12:30:00")
        self.assertIsNotNone(fallback.tzinfo)

    def test_record_status_change_skips_same_status_transition(self):
        baseline = self.defect.history.count()
        _record_status_change(self.defect, DefectStatus.NEW, DefectStatus.NEW, "owner-001")
        self.assertEqual(self.defect.history.count(), baseline)

    def test_accept_open_validates_permissions_and_inputs(self):
        invalid_cases = [
            (self.developer_actor, {"severity": "High", "priority": "P1"}, "Only Product Owner role can accept"),
            (self.other_owner_actor, {"severity": "High", "priority": "P1"}, "Only the Product Owner can accept"),
            (self.owner_actor, {"severity": "Critical", "priority": "P1"}, "Severity must be High"),
            (self.owner_actor, {"severity": "High", "priority": "P9"}, "Priority must be P1"),
        ]
        for actor, payload, message in invalid_cases:
            with self.subTest(actor=actor, payload=payload):
                with self.assertRaisesMessage(ValueError, message):
                    apply_action(self.defect, "accept_open", payload, actor)

        self.defect.status = DefectStatus.OPEN
        with self.assertRaisesMessage(ValueError, "Only New defects can be accepted."):
            apply_action(self.defect, "accept_open", {"severity": "High", "priority": "P1"}, self.owner_actor)

    def test_reject_duplicate_and_comment_guard_rails(self):
        reject_defect = self.defect
        reject_defect.status = DefectStatus.OPEN
        with self.assertRaisesMessage(ValueError, "Only New defects can be rejected."):
            apply_action(reject_defect, "reject", {}, self.owner_actor)

        fresh_reject = DefectReport.objects.create(
            report_id="BT-RP-2409",
            product=self.product,
            version="1.0.9",
            title="Reject permissions",
            description="desc",
            steps="steps",
            tester_id="tester-009",
            status=DefectStatus.NEW,
        )
        with self.assertRaisesMessage(ValueError, "Only Product Owner role can reject this defect."):
            apply_action(fresh_reject, "reject", {}, self.developer_actor)
        with self.assertRaisesMessage(ValueError, "Only the Product Owner can reject this defect."):
            apply_action(fresh_reject, "reject", {}, self.other_owner_actor)

        duplicate_defect = DefectReport.objects.create(
            report_id="BT-RP-2402",
            product=self.product,
            version="1.0.1",
            title="Duplicate branch",
            description="desc",
            steps="steps",
            tester_id="tester-002",
            status=DefectStatus.NEW,
        )
        message = apply_action(
            duplicate_defect,
            "duplicate",
            {"duplicate_of": duplicate_defect.report_id},
            self.owner_actor,
        )
        duplicate_defect.refresh_from_db()
        self.assertEqual(message, "Defect moved to Duplicate.")
        self.assertIsNone(duplicate_defect.duplicate_of)

        duplicate_role_check = DefectReport.objects.create(
            report_id="BT-RP-2403",
            product=self.product,
            version="1.0.2",
            title="Duplicate permissions",
            description="desc",
            steps="steps",
            tester_id="tester-003",
            status=DefectStatus.NEW,
        )
        with self.assertRaisesMessage(ValueError, "Only Product Owner role can mark duplicate."):
            apply_action(duplicate_role_check, "duplicate", {}, self.developer_actor)
        with self.assertRaisesMessage(ValueError, "Only the Product Owner can mark duplicate."):
            apply_action(duplicate_role_check, "duplicate", {}, self.other_owner_actor)

        duplicate_status_check = DefectReport.objects.create(
            report_id="BT-RP-2404",
            product=self.product,
            version="1.0.3",
            title="Duplicate status",
            description="desc",
            steps="steps",
            tester_id="tester-004",
            status=DefectStatus.OPEN,
        )
        with self.assertRaisesMessage(ValueError, "Only New defects can be marked duplicate."):
            apply_action(duplicate_status_check, "duplicate", {}, self.owner_actor)
        with self.assertRaisesMessage(ValueError, "Only Product Owner or Developer may add comments."):
            apply_action(self.defect, "add_comment", {"comment": "blocked"}, self.outsider_actor)

    def test_take_fix_cannot_reproduce_resolve_and_reopen_guard_rails(self):
        with self.assertRaisesMessage(ValueError, "Only Open/Reopened defects can be assigned."):
            apply_action(self.defect, "take_ownership", {}, self.developer_actor)

        self.defect.status = DefectStatus.OPEN
        with self.assertRaisesMessage(ValueError, "Only Developer role can take ownership."):
            apply_action(self.defect, "take_ownership", {}, self.owner_actor)

        self.defect.status = DefectStatus.ASSIGNED
        self.defect.assignee_id = "dev-001"

        with self.assertRaisesMessage(ValueError, "Only the assigned developer may mark this defect Fixed."):
            apply_action(
                self.defect,
                "set_fixed",
                {"fix_note": "done"},
                ActorContext(actor_id="dev-002", is_owner=False, is_developer=True),
            )
        with self.assertRaisesMessage(ValueError, "Only Developer role can set defect to Fixed."):
            apply_action(self.defect, "set_fixed", {"fix_note": "done"}, self.owner_actor)

        self.defect.status = DefectStatus.OPEN
        with self.assertRaisesMessage(ValueError, "Only Assigned defects can be marked Cannot Reproduce."):
            apply_action(self.defect, "cannot_reproduce", {"fix_note": "no repro"}, self.developer_actor)

        self.defect.status = DefectStatus.ASSIGNED
        self.defect.assignee_id = "dev-001"
        with self.assertRaisesMessage(ValueError, "Only Developer role can mark Cannot Reproduce."):
            apply_action(self.defect, "cannot_reproduce", {"fix_note": "no repro"}, self.owner_actor)
        with self.assertRaisesMessage(ValueError, "Only the assigned developer may mark this defect Cannot Reproduce."):
            apply_action(
                self.defect,
                "cannot_reproduce",
                {"fix_note": "no repro"},
                ActorContext(actor_id="dev-002", is_owner=False, is_developer=True),
            )

        self.defect.status = DefectStatus.OPEN
        with self.assertRaisesMessage(ValueError, "Only Fixed defects can be resolved."):
            apply_action(self.defect, "set_resolved", {"retest_note": "ok"}, self.owner_actor)

        self.defect.status = DefectStatus.FIXED
        with self.assertRaisesMessage(ValueError, "Only Product Owner role can resolve this defect."):
            apply_action(self.defect, "set_resolved", {"retest_note": "ok"}, self.developer_actor)
        with self.assertRaisesMessage(ValueError, "Only the Product Owner can resolve this defect."):
            apply_action(self.defect, "set_resolved", {"retest_note": "ok"}, self.other_owner_actor)

        self.defect.status = DefectStatus.OPEN
        with self.assertRaisesMessage(ValueError, "Only Fixed defects can be reopened."):
            apply_action(self.defect, "reopen", {"retest_note": "still broken"}, self.owner_actor)

        self.defect.status = DefectStatus.FIXED
        with self.assertRaisesMessage(ValueError, "Only Product Owner role can reopen this defect."):
            apply_action(self.defect, "reopen", {"retest_note": "still broken"}, self.developer_actor)
        with self.assertRaisesMessage(ValueError, "Only the Product Owner can reopen this defect."):
            apply_action(self.defect, "reopen", {"retest_note": "still broken"}, self.other_owner_actor)

    def test_unknown_action_and_register_product_validation_paths(self):
        with self.assertRaisesMessage(ValueError, "Unknown action."):
            apply_action(self.defect, "unsupported", {}, self.owner_actor)

        dev = self.create_user("dev-002", "dev2@example.com", self.developer_group)
        owner_user = type("OwnerUser", (), {"username": "owner-010"})()

        invalid_product_cases = [
            (type("OwnerUser", (), {"username": ""})(), "Prod_10", "Demo", [], "Invalid product owner account."),
            (owner_user, "", "Demo", [], "product_id cannot be empty."),
            (owner_user, "Prod_10", "", [], "name cannot be empty."),
            (owner_user, "Prod_10", "Demo", "dev-002", "developers must be an array."),
            (owner_user, "Prod_10", "Demo", ["   "], "Developer ID cannot be empty."),
            (owner_user, "Prod_10", "Demo", ["missing-dev"], "Developer account missing-dev was not found."),
        ]
        for current_owner, product_id, product_name, developer_ids, message in invalid_product_cases:
            with self.subTest(message=message):
                with self.assertRaisesMessage(ValidationError, message):
                    register_product(current_owner, product_id, product_name, developer_ids)

        product = register_product(owner_user, "Prod_10", "Demo", None)
        self.assertEqual(product.product_id, "Prod_10")
        self.assertFalse(ProductDeveloper.objects.filter(product=product).exists())

        with self.assertRaisesMessage(ValidationError, "This Product ID is already in use by another product."):
            register_product(type("OwnerUser", (), {"username": "owner-012"})(), "Prod_10", "Dupe", [])

        product_with_dedupe = register_product(
            type("OwnerUser", (), {"username": "owner-011"})(),
            "Prod_11",
            "Demo Two",
            [dev.username, dev.username],
        )
        self.assertEqual(ProductDeveloper.objects.filter(product=product_with_dedupe).count(), 1)

    def test_root_status_change_notifies_duplicate_chain(self):
        DefectReport.objects.create(
            report_id="BT-RP-2405",
            product=self.product,
            version="1.0.4",
            title="Duplicate child",
            description="desc",
            steps="steps",
            tester_id="tester-dup",
            tester_email="duplicate@example.com",
            status=DefectStatus.NEW,
            duplicate_of=self.defect,
        )

        apply_action(
            self.defect,
            "accept_open",
            {"severity": "High", "priority": "P1"},
            self.owner_actor,
        )

        self.assertEqual(len(mail.outbox), 2)
        recipients = sorted(msg.to[0] for msg in mail.outbox)
        self.assertEqual(recipients, ["duplicate@example.com", "tester@example.com"])
        self.assertIn("Duplicate Chain Notice", mail.outbox[1].subject)

    def test_non_root_transition_does_not_broadcast_to_other_duplicates(self):
        root = DefectReport.objects.create(
            report_id="BT-RP-2410",
            product=self.product,
            version="1.0.10",
            title="Root",
            description="desc",
            steps="steps",
            tester_id="tester-root",
            tester_email="root@example.com",
            status=DefectStatus.NEW,
        )
        child = DefectReport.objects.create(
            report_id="BT-RP-2411",
            product=self.product,
            version="1.0.11",
            title="Child",
            description="desc",
            steps="steps",
            tester_id="tester-child",
            tester_email="child@example.com",
            status=DefectStatus.NEW,
            duplicate_of=root,
        )
        DefectReport.objects.create(
            report_id="BT-RP-2412",
            product=self.product,
            version="1.0.12",
            title="Sibling",
            description="desc",
            steps="steps",
            tester_id="tester-sibling",
            tester_email="sibling@example.com",
            status=DefectStatus.NEW,
            duplicate_of=root,
        )

        apply_action(child, "duplicate", {"duplicate_of": root.report_id}, self.owner_actor)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["child@example.com"])

    def test_iter_duplicate_descendants_ignores_seen_nodes_in_cycles(self):
        child = DefectReport.objects.create(
            report_id="BT-RP-2414",
            product=self.product,
            version="1.0.14",
            title="Cycle child",
            description="desc",
            steps="steps",
            tester_id="tester-cycle",
            status=DefectStatus.NEW,
            duplicate_of=self.defect,
        )
        self.defect.duplicate_of = child
        self.defect.save(update_fields=["duplicate_of"])

        descendants = _iter_duplicate_descendants(self.defect)
        self.assertEqual([d.report_id for d in descendants], [child.report_id])

    def test_root_status_change_skips_duplicate_without_email(self):
        DefectReport.objects.create(
            report_id="BT-RP-2415",
            product=self.product,
            version="1.0.15",
            title="No-email duplicate",
            description="desc",
            steps="steps",
            tester_id="tester-no-email",
            tester_email="",
            status=DefectStatus.NEW,
            duplicate_of=self.defect,
        )

        apply_action(
            self.defect,
            "accept_open",
            {"severity": "High", "priority": "P1"},
            self.owner_actor,
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["tester@example.com"])

    def test_register_tenant_validates_and_persists(self):
        with self.assertRaisesMessage(ValidationError, "schema_name cannot be empty."):
            register_tenant("", "team-a.example.com")
        with self.assertRaisesMessage(ValidationError, "schema_name cannot use reserved names."):
            register_tenant("public", "team-a.example.com")
        with self.assertRaisesMessage(ValidationError, "Invalid schema_name format"):
            register_tenant("1team", "team-a.example.com")
        with self.assertRaisesMessage(ValidationError, "domain cannot be empty."):
            register_tenant("team_a", "")
        with self.assertRaisesMessage(ValidationError, "Invalid domain format"):
            register_tenant("team_a", "invalid_domain")

        tenant = register_tenant("team_a", "team-a.example.com", "Team A")
        self.assertEqual(tenant.schema_name, "team_a")
        self.assertEqual(tenant.domain, "team-a.example.com")
        self.assertTrue(Tenant.objects.filter(schema_name="team_a").exists())
        self.assertTrue(Domain.objects.filter(domain="team-a.example.com", tenant=tenant, is_primary=True).exists())

        with self.assertRaisesMessage(ValidationError, "schema_name already exists."):
            register_tenant("team_a", "team-b.example.com")
        with self.assertRaisesMessage(ValidationError, "domain already exists."):
            register_tenant("team_b", "team-a.example.com")

    def test_summarize_developer_effectiveness_requires_owner_team_membership(self):
        with self.assertRaisesMessage(ValidationError, "not in the current product owner's team"):
            summarize_developer_effectiveness("owner-001", "dev-404")

    def test_summarize_developer_effectiveness_validates_required_inputs(self):
        with self.assertRaisesMessage(ValidationError, "owner_id cannot be empty."):
            summarize_developer_effectiveness("", "dev-001")
        with self.assertRaisesMessage(ValidationError, "developer_id cannot be empty."):
            summarize_developer_effectiveness("owner-001", "")

    def test_summarize_developer_effectiveness_returns_counts(self):
        defect = DefectReport.objects.create(
            report_id="BT-RP-2413",
            product=self.product,
            version="1.0.13",
            title="Effectiveness defect",
            description="desc",
            steps="steps",
            tester_id="tester-eff",
            status=DefectStatus.NEW,
        )

        apply_action(defect, "accept_open", {"severity": "High", "priority": "P1"}, self.owner_actor)
        apply_action(defect, "take_ownership", {}, self.developer_actor)
        apply_action(defect, "set_fixed", {"fix_note": "fixed"}, self.developer_actor)
        apply_action(defect, "reopen", {"retest_note": "reopened"}, self.owner_actor)

        result = summarize_developer_effectiveness("owner-001", "dev-001")
        self.assertEqual(result["developer_id"], "dev-001")
        self.assertEqual(result["fixed"], 1)
        self.assertEqual(result["reopened"], 1)
        self.assertEqual(result["classification"], "Insufficient data")

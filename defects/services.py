from datetime import datetime
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.mail import send_mail
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from .authz import ActorContext, ROLE_DEVELOPER, ROLE_OWNER
from .models import (
    DefectComment,
    DefectReport,
    DefectStatus,
    DefectStatusHistory,
    Priority,
    Product,
    ProductDeveloper,
    Severity,
)

STATUS_STYLE = {
    DefectStatus.NEW: "status-new",
    DefectStatus.OPEN: "status-open",
    DefectStatus.ASSIGNED: "status-assigned",
    DefectStatus.FIXED: "status-fixed",
    DefectStatus.RESOLVED: "status-resolved",
    DefectStatus.REJECTED: "status-rejected",
    DefectStatus.DUPLICATE: "status-duplicate",
    DefectStatus.CANNOT_REPRODUCE: "status-cannot",
    DefectStatus.REOPENED: "status-reopened",
}

STATUS_BY_SLUG = {choice[0].lower().replace(" ", "-"): choice[0] for choice in DefectStatus.choices}
REQUIRED_CREATE_FIELDS = ("product_id", "version", "title", "description", "steps", "tester_id")

DEMO_PRODUCT_ID = "Prod_1"
DEMO_OWNER_ID = "owner-001"
DEMO_PRIMARY_DEVELOPER_ID = "dev-001"
LEGACY_DEMO_PRODUCT_ID = "PRD-1007"
LEGACY_DEMO_REPORT_IDS = {
    "BT-RP-2471",
    "BT-RP-2462",
    "BT-RP-2440",
    "BT-RP-2421",
    "BT-RP-2475",
    "BT-RP-2476",
}


def ensure_demo_seed() -> None:
    _ensure_demo_users()
    _remove_legacy_demo_seed()
    product, _ = Product.objects.get_or_create(
        product_id=DEMO_PRODUCT_ID,
        defaults={"name": "BetaTrax Demo Product", "owner_id": DEMO_OWNER_ID},
    )
    fields_to_update = []
    if product.owner_id != DEMO_OWNER_ID:
        product.owner_id = DEMO_OWNER_ID
        fields_to_update.append("owner_id")
    if product.name != "BetaTrax Demo Product":
        product.name = "BetaTrax Demo Product"
        fields_to_update.append("name")
    if fields_to_update:
        product.save(update_fields=fields_to_update)

    ProductDeveloper.objects.get_or_create(product=product, developer_id=DEMO_PRIMARY_DEVELOPER_ID)
    ProductDeveloper.objects.filter(product=product).exclude(developer_id=DEMO_PRIMARY_DEVELOPER_ID).delete()

    if DefectReport.objects.filter(product=product).exists():
        return

    seed_defects = [
        {
            "report_id": "BT-RP-1001",
            "title": "Unable to search",
            "version": "0.9.0",
            "tester_id": "Tester_1",
            "tester_email": "example@gmail.com",
            "status": DefectStatus.ASSIGNED,
            "severity": "Major",
            "priority": "High",
            "assignee_id": DEMO_PRIMARY_DEVELOPER_ID,
            "received_at": _demo_dt("2026-03-25T10:53:00+08:00"),
            "decided_at": _demo_dt("2026-03-25T11:05:00+08:00"),
            "description": "Search button unresponsive after completing an initial search",
            "steps": "1. Complete a search\n2. Modify search criteria\n3. Click Search button",
        },
        {
            "report_id": "BT-RP-1002",
            "title": "Poor readability in dark mode",
            "version": "0.9.0",
            "tester_id": "Tester_2",
            "status": DefectStatus.NEW,
            "received_at": _demo_dt("2026-03-25T20:17:00+08:00"),
            "description": "Text unclear in dark mode due to lack of contrast with background",
            "steps": "1. Enable dark mode\n2. Display text",
        },
    ]

    for row in seed_defects:
        DefectReport.objects.create(product=product, **row)


def _ensure_demo_users() -> None:
    owner_group, _ = Group.objects.get_or_create(name=ROLE_OWNER)
    developer_group, _ = Group.objects.get_or_create(name=ROLE_DEVELOPER)
    user_model = get_user_model()

    demo_users = [
        ("owner-001", "owner001@example.com", [owner_group]),
        ("dev-001", "dev001@example.com", [developer_group]),
        ("dev-004", "dev004@example.com", [developer_group]),
    ]
    for username, email, groups in demo_users:
        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )
        if created:
            user.set_password("Pass1234!")
            user.save(update_fields=["password"])
        for group in groups:
            user.groups.add(group)


def _remove_legacy_demo_seed() -> None:
    legacy_product = Product.objects.filter(product_id=LEGACY_DEMO_PRODUCT_ID).first()
    if legacy_product is not None:
        legacy_defects = DefectReport.objects.filter(product=legacy_product)
        DefectComment.objects.filter(defect__in=legacy_defects).delete()
        DefectStatusHistory.objects.filter(defect__in=legacy_defects).delete()
        legacy_defects.delete()
        ProductDeveloper.objects.filter(product=legacy_product).delete()
        legacy_product.delete()

    stale_reports = DefectReport.objects.filter(report_id__in=LEGACY_DEMO_REPORT_IDS)
    if stale_reports.exists():
        DefectComment.objects.filter(defect__in=stale_reports).delete()
        DefectStatusHistory.objects.filter(defect__in=stale_reports).delete()
        stale_reports.delete()


def _demo_dt(value: str):
    parsed = parse_datetime(value)
    if parsed is not None:
        return parsed
    return timezone.make_aware(datetime.fromisoformat(value), timezone.get_current_timezone())


def next_report_id() -> str:
    highest = 2400
    for report_id in DefectReport.objects.values_list("report_id", flat=True):
        try:
            highest = max(highest, int(report_id.rsplit("-", 1)[-1]))
        except (TypeError, ValueError):
            continue
    return f"BT-RP-{highest + 1}"


def serialize_defect(defect: DefectReport) -> dict[str, Any]:
    return {
        "id": defect.report_id,
        "title": defect.title,
        "product_id": defect.product_id,
        "version": defect.version,
        "tester_id": defect.tester_id,
        "email": defect.tester_email,
        "status": defect.status,
        "severity": defect.severity,
        "priority": defect.priority,
        "backlog_ref": defect.backlog_ref,
        "assignee": defect.assignee_id,
        "description": defect.description,
        "steps": defect.steps,
        "fix_note": defect.fix_note,
        "retest_note": defect.retest_note,
        "badge_class": STATUS_STYLE.get(defect.status, ""),
    }


def serialize_defect_for_api(defect: DefectReport) -> dict[str, Any]:
    return {
        "report_id": defect.report_id,
        "title": defect.title,
        "product_id": defect.product_id,
        "version": defect.version,
        "tester_id": defect.tester_id,
        "status": defect.status,
        "severity": defect.severity,
        "priority": defect.priority,
        "assignee_id": defect.assignee_id,
        "received_at": defect.received_at.isoformat(),
    }


def serialize_defect_detail_for_api(defect: DefectReport) -> dict[str, Any]:
    return {
        "report_id": defect.report_id,
        "product_id": defect.product_id,
        "version": defect.version,
        "title": defect.title,
        "description": defect.description,
        "steps": defect.steps,
        "tester_id": defect.tester_id,
        "email": defect.tester_email,
        "status": defect.status,
        "severity": defect.severity,
        "priority": defect.priority,
        "assignee_id": defect.assignee_id,
        "fix_note": defect.fix_note,
        "retest_note": defect.retest_note,
        "received_at": defect.received_at.isoformat(),
        "decided_at": defect.decided_at.isoformat() if defect.decided_at else None,
    }


def create_defect(data: dict[str, Any]) -> DefectReport:
    report_id = next_report_id()
    defect = DefectReport.objects.create(
        report_id=report_id,
        product=data["product"],
        version=data["version"],
        title=data["title"],
        description=data["description"],
        steps=data["steps"],
        tester_id=data["tester_id"],
        tester_email=data.get("email", ""),
        status=DefectStatus.NEW,
    )
    DefectStatusHistory.objects.create(
        defect=defect,
        from_status=DefectStatus.NEW,
        to_status=DefectStatus.NEW,
        actor_id=defect.tester_id,
    )
    return defect


def _record_status_change(defect: DefectReport, from_status: str, to_status: str, actor_id: str = "") -> None:
    if from_status == to_status:
        return
    DefectStatusHistory.objects.create(
        defect=defect,
        from_status=from_status,
        to_status=to_status,
        actor_id=actor_id,
    )


def _notify_status_change(defect: DefectReport) -> None:
    if not defect.tester_email:
        return
    send_mail(
        subject=f"[BetaTrax] {defect.report_id} status changed to {defect.status}",
        message=(
            f"Defect {defect.report_id} ({defect.title}) is now {defect.status}.\n"
            f"Product: {defect.product_id}\n"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[defect.tester_email],
        fail_silently=True,
    )


def apply_action(defect: DefectReport, action: str, payload: dict[str, Any], actor: ActorContext) -> str:
    current = defect.status

    if action == "accept_open":
        if current != DefectStatus.NEW:
            raise ValueError("Only New defects can be accepted.")
        if not actor.is_owner:
            raise ValueError("Only Product Owner role can accept this defect.")
        if actor.actor_id != defect.product.owner_id:
            raise ValueError("Only the Product Owner can accept this defect.")
        severity = (payload.get("severity") or "").strip()
        priority = (payload.get("priority") or "").strip()
        if severity not in set(Severity.values):
            raise ValueError("Severity must be High, Medium, or Low.")
        if priority not in set(Priority.values):
            raise ValueError("Priority must be P1, P2, or P3.")
        defect.severity = severity
        defect.priority = priority
        defect.backlog_ref = (payload.get("backlog_ref") or "").strip()
        defect.status = DefectStatus.OPEN
        defect.decided_at = timezone.now()
        defect.save(update_fields=["severity", "priority", "backlog_ref", "status", "decided_at", "updated_at"])
        _record_status_change(defect, current, defect.status, actor.actor_id)
        _notify_status_change(defect)
        return "Defect accepted and moved to Open."

    if action == "reject":
        if current != DefectStatus.NEW:
            raise ValueError("Only New defects can be rejected.")
        if not actor.is_owner:
            raise ValueError("Only Product Owner role can reject this defect.")
        if actor.actor_id != defect.product.owner_id:
            raise ValueError("Only the Product Owner can reject this defect.")
        defect.status = DefectStatus.REJECTED
        defect.decided_at = timezone.now()
        defect.save(update_fields=["status", "decided_at", "updated_at"])
        _record_status_change(defect, current, defect.status, actor.actor_id)
        _notify_status_change(defect)
        return "Defect moved to Rejected."

    if action == "duplicate":
        if current != DefectStatus.NEW:
            raise ValueError("Only New defects can be marked duplicate.")
        if not actor.is_owner:
            raise ValueError("Only Product Owner role can mark duplicate.")
        if actor.actor_id != defect.product.owner_id:
            raise ValueError("Only the Product Owner can mark duplicate.")
        duplicate_of = (payload.get("duplicate_of") or "").strip()
        if duplicate_of and duplicate_of != defect.report_id:
            parent = DefectReport.objects.filter(report_id=duplicate_of).first()
            if parent is None:
                raise ValueError("Duplicate target report does not exist.")
            defect.duplicate_of = parent
        defect.status = DefectStatus.DUPLICATE
        defect.decided_at = timezone.now()
        defect.save(update_fields=["duplicate_of", "status", "decided_at", "updated_at"])
        _record_status_change(defect, current, defect.status, actor.actor_id)
        _notify_status_change(defect)
        return "Defect moved to Duplicate."

    if action == "take_ownership":
        if current not in {DefectStatus.OPEN, DefectStatus.REOPENED}:
            raise ValueError("Only Open/Reopened defects can be assigned.")
        if not actor.is_developer:
            raise ValueError("Only Developer role can take ownership.")
        if not ProductDeveloper.objects.filter(product=defect.product, developer_id=actor.actor_id).exists():
            raise ValueError("Only developers on the product team may take ownership.")
        defect.assignee_id = actor.actor_id
        defect.status = DefectStatus.ASSIGNED
        defect.decided_at = timezone.now()
        defect.save(update_fields=["assignee_id", "status", "decided_at", "updated_at"])
        _record_status_change(defect, current, defect.status, actor.actor_id)
        _notify_status_change(defect)
        return f"Assigned to {actor.actor_id}."

    if action == "set_fixed":
        if current != DefectStatus.ASSIGNED:
            raise ValueError("Only Assigned defects can be set to Fixed.")
        if not actor.is_developer:
            raise ValueError("Only Developer role can set defect to Fixed.")
        if not defect.assignee_id or actor.actor_id != defect.assignee_id:
            raise ValueError("Only the assigned developer may mark this defect Fixed.")
        defect.fix_note = (payload.get("fix_note") or "").strip()
        defect.status = DefectStatus.FIXED
        defect.decided_at = timezone.now()
        defect.save(update_fields=["fix_note", "status", "decided_at", "updated_at"])
        _record_status_change(defect, current, defect.status, actor.actor_id)
        _notify_status_change(defect)
        return "Defect moved to Fixed."

    if action == "cannot_reproduce":
        if current != DefectStatus.ASSIGNED:
            raise ValueError("Only Assigned defects can be marked Cannot Reproduce.")
        if not actor.is_developer:
            raise ValueError("Only Developer role can mark Cannot Reproduce.")
        if not defect.assignee_id or actor.actor_id != defect.assignee_id:
            raise ValueError("Only the assigned developer may mark this defect Cannot Reproduce.")
        defect.fix_note = (payload.get("fix_note") or "").strip()
        defect.status = DefectStatus.CANNOT_REPRODUCE
        defect.decided_at = timezone.now()
        defect.save(update_fields=["fix_note", "status", "decided_at", "updated_at"])
        _record_status_change(defect, current, defect.status, actor.actor_id)
        _notify_status_change(defect)
        return "Defect moved to Cannot Reproduce."

    if action == "set_resolved":
        if current != DefectStatus.FIXED:
            raise ValueError("Only Fixed defects can be resolved.")
        if not actor.is_owner:
            raise ValueError("Only Product Owner role can resolve this defect.")
        if actor.actor_id != defect.product.owner_id:
            raise ValueError("Only the Product Owner can resolve this defect.")
        defect.retest_note = (payload.get("retest_note") or "").strip()
        defect.status = DefectStatus.RESOLVED
        defect.decided_at = timezone.now()
        defect.save(update_fields=["retest_note", "status", "decided_at", "updated_at"])
        _record_status_change(defect, current, defect.status, actor.actor_id)
        _notify_status_change(defect)
        return "Defect moved to Resolved."

    if action == "reopen":
        if current != DefectStatus.FIXED:
            raise ValueError("Only Fixed defects can be reopened.")
        if not actor.is_owner:
            raise ValueError("Only Product Owner role can reopen this defect.")
        if actor.actor_id != defect.product.owner_id:
            raise ValueError("Only the Product Owner can reopen this defect.")
        defect.retest_note = (payload.get("retest_note") or "").strip()
        defect.status = DefectStatus.REOPENED
        defect.decided_at = timezone.now()
        defect.save(update_fields=["retest_note", "status", "decided_at", "updated_at"])
        _record_status_change(defect, current, defect.status, actor.actor_id)
        _notify_status_change(defect)
        return "Defect moved to Reopened."

    if action == "add_comment":
        comment = (payload.get("comment") or "").strip()
        if not actor.is_owner and not actor.is_developer:
            raise ValueError("Only Product Owner or Developer may add comments.")
        if not comment:
            raise ValueError("Comment text is required.")
        DefectComment.objects.create(defect=defect, author_id=actor.actor_id, text=comment)
        return "Comment added."

    raise ValueError("Unknown action.")

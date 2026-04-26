from datetime import datetime
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.mail import send_mail
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.core.exceptions import ValidationError

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
from .effectiveness import classify_developer

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


def _iter_duplicate_descendants(root_defect: DefectReport) -> list[DefectReport]:
    descendants: list[DefectReport] = []
    seen_ids = {root_defect.report_id}
    queue = [root_defect.report_id]
    head = 0

    while head < len(queue):
        parent_id = queue[head]
        head += 1
        children = list(DefectReport.objects.filter(duplicate_of_id=parent_id).order_by("report_id"))
        for child in children:
            if child.report_id in seen_ids:
                continue
            seen_ids.add(child.report_id)
            descendants.append(child)
            queue.append(child.report_id)

    return descendants


def _notify_duplicate_chain_on_root_change(defect: DefectReport) -> None:
    if defect.duplicate_of_id:
        return

    for linked in _iter_duplicate_descendants(defect):
        if not linked.tester_email:
            continue
        send_mail(
            subject=f"[BetaTrax] Duplicate Chain Notice: Root defect {defect.report_id} changed to {defect.status}",
            message=(
                f"Your duplicate defect {linked.report_id} is linked to root defect {defect.report_id}.\n"
                f"Current root defect status: {defect.status}\n"
                f"Product: {defect.product_id}\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[linked.tester_email],
            fail_silently=True,
        )


def _notify_transition(defect: DefectReport) -> None:
    _notify_status_change(defect)
    _notify_duplicate_chain_on_root_change(defect)


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
        _notify_transition(defect)
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
        _notify_transition(defect)
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
        _notify_transition(defect)
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
        _notify_transition(defect)
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
        _notify_transition(defect)
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
        _notify_transition(defect)
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
        _notify_transition(defect)
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
        _notify_transition(defect)
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

def register_product(owner_user, product_id, product_name, developer_ids):
    owner_id = (getattr(owner_user, "username", "") or "").strip()
    product_id = (product_id or "").strip()
    product_name = (product_name or "").strip()

    if not owner_id:
        raise ValidationError("Invalid product owner account.")
    if not product_id:
        raise ValidationError("product_id cannot be empty.")
    if not product_name:
        raise ValidationError("name cannot be empty.")

    # Rule 1: one owner can register at most one product in this flow.
    if Product.objects.filter(owner_id=owner_id).exists():
        raise ValidationError("You have already registered a product and cannot register another.")

    # Rule 2: Product ID must be unique.
    if Product.objects.filter(product_id=product_id).exists():
        raise ValidationError("This Product ID is already in use by another product.")

    if developer_ids is None:
        developer_ids = []
    if not isinstance(developer_ids, list):
        raise ValidationError("developers must be an array.")
    developer_ids = list(dict.fromkeys(developer_ids))

    # Rule 3: developers must exist, be in developer group, and unassigned.
    user_model = get_user_model()
    developers_to_assign: list[str] = []
    for raw_dev_id in developer_ids:
        developer_id = str(raw_dev_id).strip()
        if not developer_id:
            raise ValidationError("Developer ID cannot be empty.")

        dev = user_model.objects.filter(username=developer_id).first()
        if not dev or not dev.groups.filter(name=ROLE_DEVELOPER).exists():
            raise ValidationError(f"Developer account {developer_id} was not found.")

        if ProductDeveloper.objects.filter(developer_id=developer_id).exists():
            raise ValidationError(f"Developer {developer_id} is already assigned to another product.")

        developers_to_assign.append(developer_id)

    # Create product and bind developers using username IDs.
    new_product = Product.objects.create(
        product_id=product_id,
        name=product_name,
        owner_id=owner_id,
    )

    for developer_id in developers_to_assign:
        ProductDeveloper.objects.create(product=new_product, developer_id=developer_id)

    return new_product


def summarize_developer_effectiveness(owner_id: str, developer_id: str) -> dict[str, Any]:
    normalized_owner = (owner_id or "").strip()
    normalized_developer = (developer_id or "").strip()

    if not normalized_owner:
        raise ValidationError("owner_id cannot be empty.")
    if not normalized_developer:
        raise ValidationError("developer_id cannot be empty.")

    in_owner_team = ProductDeveloper.objects.filter(
        product__owner_id=normalized_owner,
        developer_id=normalized_developer,
    ).exists()
    if not in_owner_team:
        raise ValidationError("The developer is not in the current product owner's team.")

    owner_defects = DefectReport.objects.filter(
        product__owner_id=normalized_owner,
        assignee_id=normalized_developer,
    )
    fixed_count = DefectStatusHistory.objects.filter(
        defect__in=owner_defects,
        to_status=DefectStatus.FIXED,
        actor_id=normalized_developer,
    ).count()
    reopened_count = DefectStatusHistory.objects.filter(
        defect__in=owner_defects,
        to_status=DefectStatus.REOPENED,
    ).count()

    classification = classify_developer(fixed_count, reopened_count)
    ratio = (reopened_count / fixed_count) if fixed_count else None
    return {
        "developer_id": normalized_developer,
        "fixed": fixed_count,
        "reopened": reopened_count,
        "reopen_ratio": ratio,
        "classification": classification,
    }

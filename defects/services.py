from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.mail import send_mail
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


def ensure_demo_seed() -> None:
    _ensure_demo_users()
    product, _ = Product.objects.get_or_create(
        product_id="PRD-1007",
        defaults={"name": "BetaTrax Demo Product", "owner_id": "owner-001"},
    )
    if product.owner_id != "owner-001":
        product.owner_id = "owner-001"
        product.save(update_fields=["owner_id"])

    ProductDeveloper.objects.get_or_create(product=product, developer_id="dev-001")
    ProductDeveloper.objects.get_or_create(product=product, developer_id="dev-004")

    if DefectReport.objects.exists():
        return

    seed_defects = [
        {
            "report_id": "BT-RP-2471",
            "title": "App crashes after Save",
            "version": "v1.4.3-beta",
            "tester_id": "tester-008",
            "tester_email": "tester@example.com",
            "status": DefectStatus.NEW,
            "description": "When user clicks Save on dashboard settings, app crashes and returns to login.",
            "steps": "1) Open settings\n2) Change a value\n3) Click Save",
        },
        {
            "report_id": "BT-RP-2462",
            "title": "Login timeout in beta region",
            "version": "v1.4.2-beta",
            "tester_id": "tester-014",
            "status": DefectStatus.OPEN,
            "severity": Severity.HIGH,
            "priority": Priority.P1,
            "backlog_ref": "BETA-249",
            "description": "Users in HK region are logged out before session initialization.",
            "steps": "1) Login\n2) Wait for redirect\n3) Session expires",
        },
        {
            "report_id": "BT-RP-2440",
            "title": "Export CSV has wrong delimiter",
            "version": "v1.4.2-beta",
            "tester_id": "tester-020",
            "tester_email": "qa@example.com",
            "status": DefectStatus.ASSIGNED,
            "severity": Severity.MEDIUM,
            "priority": Priority.P2,
            "backlog_ref": "BETA-251",
            "assignee_id": "dev-001",
            "description": "CSV export uses semicolon and breaks spreadsheet import in default locale.",
            "steps": "1) Export report\n2) Open in Excel\n3) Values collapse into one column",
        },
        {
            "report_id": "BT-RP-2421",
            "title": "Search index not refreshed",
            "version": "v1.4.1-beta",
            "tester_id": "tester-003",
            "tester_email": "tester3@example.com",
            "status": DefectStatus.FIXED,
            "severity": Severity.LOW,
            "priority": Priority.P3,
            "backlog_ref": "BETA-199",
            "assignee_id": "dev-004",
            "fix_note": "Invalidate index cache after save.",
            "description": "Recent updates are not searchable until a full reindex job runs.",
            "steps": "1) Update content\n2) Search with keyword\n3) No result",
        },
        {
            "report_id": "BT-RP-2475",
            "title": "Notification badge count is off by one",
            "version": "v1.4.3-beta",
            "tester_id": "tester-031",
            "tester_email": "tester31@example.com",
            "status": DefectStatus.OPEN,
            "severity": Severity.MEDIUM,
            "priority": Priority.P2,
            "backlog_ref": "BETA-312",
            "description": "Header badge shows one extra unread item after viewing latest alert.",
            "steps": "1) Open notifications\n2) Read newest alert\n3) Return to dashboard",
        },
        {
            "report_id": "BT-RP-2476",
            "title": "Dark text overlaps chart legend on small screens",
            "version": "v1.4.3-beta",
            "tester_id": "tester-044",
            "status": DefectStatus.RESOLVED,
            "severity": Severity.LOW,
            "priority": Priority.P3,
            "backlog_ref": "BETA-318",
            "assignee_id": "dev-001",
            "fix_note": "Adjusted legend spacing and font size breakpoints.",
            "retest_note": "Verified on 390x844 viewport.",
            "description": "Analytics chart legend overlaps labels in mobile layout.",
            "steps": "1) Open analytics page on phone\n2) Switch to weekly chart\n3) Observe legend overlap",
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

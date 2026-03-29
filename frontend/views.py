from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render

from defects.authz import actor_from_user
from defects.models import DefectReport, Product
from defects.services import (
    REQUIRED_CREATE_FIELDS,
    STATUS_BY_SLUG,
    apply_action,
    create_defect as create_defect_record,
    ensure_demo_seed,
    serialize_defect,
)


@login_required(login_url="frontend:external-auth")
def home(request):
    ensure_demo_seed()
    actor = actor_from_user(request.user)
    if not actor.is_owner and not actor.is_developer:
        messages.error(request, "Only Product Owner or Developer can access the defect board.")
        return redirect("frontend:external-auth")

    selected = request.GET.get("status", "all").strip()
    queryset = DefectReport.objects.select_related("product").order_by("-report_id")
    if actor.is_owner:
        queryset = queryset.filter(product__owner_id=actor.actor_id)
    elif actor.is_developer:
        queryset = queryset.filter(product__developers__developer_id=actor.actor_id).distinct()

    if selected != "all":
        status = STATUS_BY_SLUG.get(selected)
        if actor.is_developer and status == "New":
            queryset = queryset.none()
        elif status:
            queryset = queryset.filter(status=status)
        else:
            queryset = queryset.none()

    defects = [serialize_defect(defect) for defect in queryset]
    return render(
        request,
        "frontend/home.html",
        {"defects": defects, "selected_status": selected},
    )


def external_auth(request):
    ensure_demo_seed()
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        user = authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, "Invalid username or password.")
        else:
            login(request, user)
            return redirect("frontend:home")

    return render(request, "frontend/auth.html")


def sign_out(request):
    logout(request)
    messages.success(request, "Signed out.")
    return redirect("frontend:external-auth")


@login_required(login_url="frontend:external-auth")
@transaction.atomic
def create_defect(request):
    ensure_demo_seed()
    actor = actor_from_user(request.user)
    if not actor.is_owner:
        messages.error(request, "Only Product Owner can create new defects from this screen.")
        return redirect("frontend:home")

    if request.method != "POST":
        return render(request, "frontend/new_defect.html")

    fields = {key: request.POST.get(key, "").strip() for key in REQUIRED_CREATE_FIELDS}
    fields["email"] = request.POST.get("email", "").strip()
    missing = [name for name in REQUIRED_CREATE_FIELDS if not fields[name]]
    if missing:
        messages.error(request, f"Missing required fields: {', '.join(missing)}")
        return redirect("frontend:create-defect")

    product = Product.objects.filter(product_id=fields["product_id"]).first()
    if product is None:
        messages.error(request, "Unknown Product ID.")
        return redirect("frontend:create-defect")

    defect = create_defect_record(
        {
            "product": product,
            "version": fields["version"],
            "title": fields["title"],
            "description": fields["description"],
            "steps": fields["steps"],
            "tester_id": fields["tester_id"],
            "email": fields["email"],
        }
    )
    messages.success(request, f"Defect {defect.report_id} created with status New.")
    return redirect("frontend:defect-detail", defect_id=defect.report_id)


@login_required(login_url="frontend:external-auth")
@transaction.atomic
def defect_detail(request, defect_id):
    ensure_demo_seed()
    defect = DefectReport.objects.select_related("product").filter(report_id=defect_id).first()
    if defect is None:
        raise Http404("Defect not found")

    actor = actor_from_user(request.user)
    if actor.is_owner and defect.product.owner_id != actor.actor_id:
        raise Http404("Defect not found")
    if actor.is_developer and not defect.product.developers.filter(developer_id=actor.actor_id).exists():
        raise Http404("Defect not found")
    if actor.is_developer and defect.status == "New":
        raise Http404("Defect not found")
    if not actor.is_owner and not actor.is_developer:
        messages.error(request, "Only Product Owner or Developer can access defect details.")
        return redirect("frontend:external-auth")

    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        try:
            msg = apply_action(defect, action, request.POST, actor)
            messages.success(request, msg)
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("frontend:defect-detail", defect_id=defect_id)

    payload = serialize_defect(defect)
    payload["comments"] = [
        {"author": comment.author_id, "text": comment.text}
        for comment in defect.comments.all()
    ]
    return render(request, "frontend/defect_detail.html", {"defect": payload})

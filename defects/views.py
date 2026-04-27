from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .services import register_product
from .authz import actor_from_user
from .models import DefectReport, Product
from django.core.exceptions import ValidationError
from .serializers import (
    AuthenticationErrorResponseSerializer,
    DEFECT_ACTION_CHOICES,
    DEFECT_STATUS_VALUES,
    DefectActionRequestDocSerializer,
    DefectActionResponseSerializer,
    DefectCreateBadRequestResponseSerializer,
    DefectActionSerializer,
    DefectCreateRequestDocSerializer,
    DefectCreateResponseSerializer,
    DefectCreateSerializer,
    DefectDetailResponseSerializer,
    DefectListResponseSerializer,
    DeveloperEffectivenessResponseSerializer,
    ErrorResponseSerializer,
    MissingFieldsErrorResponseSerializer,
    ProductRegisterRequestSerializer,
    ProductRegisterResponseSerializer,
)
from .services import (
    STATUS_BY_SLUG,
    apply_action,
    create_defect,
    serialize_defect_detail_for_api,
    serialize_defect_for_api,
    summarize_developer_effectiveness,
)

try:
    from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
except Exception:  # pragma: no cover - optional dependency fallback
    class OpenApiParameter:  # type: ignore[override]
        QUERY = "query"
        PATH = "path"

        def __init__(self, *args, **kwargs):
            pass

    class OpenApiResponse:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            pass

    def extend_schema(*args, **kwargs):  # type: ignore[override]
        def _decorator(obj):
            return obj

        return _decorator

class ProductRegisterApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="registerProduct",
        summary="Register product in current tenant",
        description=(
            "Requires Swagger Authorize/basicAuth or a valid session cookie. "
            "Only Product Owners can register a product and bind developer accounts in one request. "
            "Use this endpoint to create a product visible inside the current database scope. "
            "All request fields remain editable in Swagger UI; no preset example payload is required."
        ),
        request=ProductRegisterRequestSerializer,
        responses={
            201: OpenApiResponse(ProductRegisterResponseSerializer, description="Product registered."),
            400: OpenApiResponse(ErrorResponseSerializer, description="Validation failed."),
            403: OpenApiResponse(
                AuthenticationErrorResponseSerializer,
                description="Authentication is missing or the authenticated user is not a Product Owner.",
            ),
        },
    )
    def post(self, request):
        actor = actor_from_user(request.user)
        if not actor.is_owner:
            return Response({"error": "Only Product Owner can register products"}, status=403)

        try:
            product = register_product(
                owner_user=request.user,
                product_id=request.data.get('product_id'),
                product_name=request.data.get('name'),
                developer_ids=request.data.get('developers', [])
            )
            return Response({"message": "Product registered successfully", "product_id": product.product_id}, status=201)
        except ValidationError as e:
            detail = e.messages[0] if getattr(e, "messages", None) else str(e)
            return Response({"error": detail}, status=400)
        
class DefectCreateApi(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    @extend_schema(
        operation_id="submitDefect",
        summary="Submit defect",
        description=(
            "Create a new defect report from an external testing system. "
            "Authentication is optional for this endpoint. "
            "All request fields can be edited freely in Swagger UI to support ad hoc manual testing."
        ),
        request=DefectCreateRequestDocSerializer,
        responses={
            201: OpenApiResponse(DefectCreateResponseSerializer, description="Defect submitted."),
            400: OpenApiResponse(
                DefectCreateBadRequestResponseSerializer,
                description="Required fields are missing/blank or serializer validation failed.",
            ),
            404: OpenApiResponse(ErrorResponseSerializer, description="Product ID was not found."),
        },
    )
    def post(self, request):
        serializer = DefectCreateSerializer(data=request.data)
        if not serializer.is_valid():
            details = serializer.errors
            if "missing_fields" in details:
                return Response(
                    {"error": "Missing required fields.", "missing_fields": details["missing_fields"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response({"error": details}, status=status.HTTP_400_BAD_REQUEST)

        payload = serializer.validated_data
        product = Product.objects.filter(product_id=payload["product_id"]).first()
        if product is None:
            return Response({"error": "Unknown Product ID."}, status=status.HTTP_404_NOT_FOUND)

        defect = create_defect(
            {
                "product": product,
                "version": payload["version"],
                "title": payload["title"],
                "description": payload["description"],
                "steps": payload["steps"],
                "tester_id": payload["tester_id"],
                "email": payload.get("email", ""),
            }
        )

        return Response(
            {
                "report_id": defect.report_id,
                "status": defect.status,
                "required_fields": ["product_id", "version", "title", "description", "steps", "tester_id"],
            },
            status=status.HTTP_201_CREATED,
        )


class DefectListApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="listDefects",
        summary="List defects visible to current user",
        description=(
            "Requires Swagger Authorize/basicAuth or a valid session cookie. "
            "List defects by filters. Product Owners and Developers have different visibility scopes. "
            "This endpoint returns only defects visible to the authenticated user after role-based filtering "
            "and optional status/product filters are applied."
        ),
        parameters=[
            OpenApiParameter(
                name="status",
                location=OpenApiParameter.QUERY,
                required=False,
                type=str,
                enum=list(DEFECT_STATUS_VALUES),
                description="Filter by defect lifecycle status.",
            ),
            OpenApiParameter(
                name="product_id",
                location=OpenApiParameter.QUERY,
                required=False,
                type=str,
                description="Filter to one product ID.",
            ),
        ],
        responses={
            200: OpenApiResponse(DefectListResponseSerializer, description="Visible defects returned."),
            403: OpenApiResponse(
                AuthenticationErrorResponseSerializer,
                description="Authentication is missing or the user role is not allowed.",
            ),
        },
    )
    def get(self, request):
        actor = actor_from_user(request.user)
        if not actor.is_owner and not actor.is_developer:
            return Response({"error": "Only Product Owner or Developer can view defects."}, status=status.HTTP_403_FORBIDDEN)

        queryset = DefectReport.objects.select_related("product").order_by("-received_at")

        status_value = str(request.query_params.get("status", "")).strip()
        if status_value:
            desired = STATUS_BY_SLUG.get(status_value.lower().replace(" ", "-"), status_value)
            if actor.is_developer and desired == "New":
                return Response({"error": "Developer cannot access New defects."}, status=status.HTTP_403_FORBIDDEN)
            queryset = queryset.filter(status=desired)

        product_id = str(request.query_params.get("product_id", "")).strip()
        if product_id:
            queryset = queryset.filter(product_id=product_id)

        if actor.is_owner:
            queryset = queryset.filter(product__owner_id=actor.actor_id)
        else:
            queryset = queryset.filter(product__developers__developer_id=actor.actor_id).distinct()

        return Response({"items": [serialize_defect_for_api(defect) for defect in queryset]})


class DefectDetailApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="getDefectDetail",
        summary="Get defect detail by report ID",
        description=(
            "Requires Swagger Authorize/basicAuth or a valid session cookie. "
            "Retrieve detailed defect information by report_id. Product Owners can access defects in their own "
            "products. Developers can access defects assigned to products they belong to, except defects still in "
            "the New state."
        ),
        parameters=[
            OpenApiParameter(
                name="defect_id",
                location=OpenApiParameter.PATH,
                required=True,
                type=str,
                description="Defect report ID, for example BT-RP-2477.",
            )
        ],
        responses={
            200: OpenApiResponse(DefectDetailResponseSerializer, description="Defect detail returned."),
            403: OpenApiResponse(
                AuthenticationErrorResponseSerializer,
                description="Authentication is missing or the user cannot access this defect.",
            ),
            404: OpenApiResponse(ErrorResponseSerializer, description="Defect does not exist or is outside the user's scope."),
        },
    )
    def get(self, request, defect_id):
        defect = DefectReport.objects.select_related("product").filter(report_id=defect_id).first()
        if defect is None:
            return Response({"error": "Defect not found."}, status=status.HTTP_404_NOT_FOUND)

        actor = actor_from_user(request.user)
        if not actor.is_owner and not actor.is_developer:
            return Response({"error": "Only Product Owner or Developer can view defect details."}, status=status.HTTP_403_FORBIDDEN)

        if actor.is_owner:
            if defect.product.owner_id != actor.actor_id:
                return Response({"error": "Defect not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            if defect.status == "New":
                return Response({"error": "Developer cannot access New defects."}, status=status.HTTP_403_FORBIDDEN)
            if not defect.product.developers.filter(developer_id=actor.actor_id).exists():
                return Response({"error": "Defect not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(serialize_defect_detail_for_api(defect))


class DefectActionApi(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    @extend_schema(
        operation_id="applyDefectAction",
        summary="Apply workflow action to a defect",
        description=(
            "Requires Swagger Authorize/basicAuth or a valid session cookie. "
            "Apply one lifecycle or comment action to a defect. Supported actions: "
            + ", ".join(DEFECT_ACTION_CHOICES)
            + ". Role and current-status rules are enforced by the API.\n\n"
            "Action-specific payload rules:\n"
            "- accept_open: Product Owner only; valid when status is New; requires severity and priority; backlog_ref optional.\n"
            "- reject: Product Owner only; valid when status is New.\n"
            "- duplicate: Product Owner only; valid when status is New; requires duplicate_of root report ID.\n"
            "- take_ownership: Developer only; valid when status is Open.\n"
            "- set_fixed: Assigned developer only; valid when status is Assigned; fix_note optional.\n"
            "- cannot_reproduce: Assigned developer only; valid when status is Assigned; fix_note optional.\n"
            "- set_resolved: Product Owner only; valid when status is Fixed; retest_note optional.\n"
            "- reopen: Product Owner only; valid when status is Fixed; retest_note required by business workflow.\n"
            "- add_comment: Authenticated Product Owner or Developer; comment must not be empty.\n\n"
            "Swagger UI keeps every request field editable so you can test arbitrary payload combinations instead of "
            "starting from hard-coded examples."
        ),
        parameters=[
            OpenApiParameter(
                name="defect_id",
                location=OpenApiParameter.PATH,
                required=True,
                type=str,
                description="Defect report ID to transition.",
            )
        ],
        request=DefectActionRequestDocSerializer,
        responses={
            200: OpenApiResponse(DefectActionResponseSerializer, description="Action applied."),
            400: OpenApiResponse(ErrorResponseSerializer, description="Action is invalid for the payload or current status."),
            403: OpenApiResponse(
                AuthenticationErrorResponseSerializer,
                description="Authentication is missing or the authenticated user cannot perform the action.",
            ),
            404: OpenApiResponse(ErrorResponseSerializer, description="Defect was not found."),
        },
    )
    def post(self, request, defect_id):
        defect = DefectReport.objects.select_related("product").filter(report_id=defect_id).first()
        if defect is None:
            return Response({"error": "Defect not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = DefectActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        payload = serializer.validated_data
        actor = actor_from_user(request.user)
        if not actor.actor_id:
            return Response({"error": "Authentication required."}, status=status.HTTP_403_FORBIDDEN)
        action = str(payload.get("action", "")).strip()
        try:
            message = apply_action(defect, action, payload, actor)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "message": message,
                "report_id": defect.report_id,
                "status": defect.status,
            }
        )


class DeveloperEffectivenessApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="getDeveloperEffectiveness",
        summary="Get developer effectiveness classification",
        description=(
            "Requires Swagger Authorize/basicAuth or a valid session cookie. "
            "Only Product Owners can query effectiveness classification for developers in their teams. "
            "Classification uses fixed count and reopened ratio. Thresholds are: fixed < 20 -> Insufficient data; "
            "reopened/fixed < 1/32 -> Good; reopened/fixed < 1/8 -> Fair; otherwise -> Poor."
        ),
        parameters=[
            OpenApiParameter(
                name="developer_id",
                location=OpenApiParameter.PATH,
                required=True,
                type=str,
                description="Developer username to classify.",
            )
        ],
        responses={
            200: OpenApiResponse(DeveloperEffectivenessResponseSerializer, description="Effectiveness metric returned."),
            400: OpenApiResponse(ErrorResponseSerializer, description="Developer is not in the owner's team or input is invalid."),
            403: OpenApiResponse(
                AuthenticationErrorResponseSerializer,
                description="Authentication is missing or the authenticated user is not a Product Owner.",
            ),
        },
    )
    def get(self, request, developer_id):
        actor = actor_from_user(request.user)
        if not actor.is_owner:
            return Response({"error": "Only product owners can view developer effectiveness."}, status=status.HTTP_403_FORBIDDEN)

        try:
            result = summarize_developer_effectiveness(actor.actor_id, developer_id)
        except ValidationError as exc:
            detail = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            return Response({"error": detail}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)

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
    DEFECT_ACTION_CHOICES,
    DEFECT_STATUS_VALUES,
    DefectActionRequestDocSerializer,
    DefectActionResponseSerializer,
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
    from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
except Exception:  # pragma: no cover - optional dependency fallback
    class OpenApiExample:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            pass

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
        summary="Register product",
        description="Only Product Owners can register a product and bind developer accounts in one request.",
        request=ProductRegisterRequestSerializer,
        responses={
            201: OpenApiResponse(ProductRegisterResponseSerializer, description="Product registered."),
            400: OpenApiResponse(ErrorResponseSerializer, description="Validation failed."),
            403: OpenApiResponse(ErrorResponseSerializer, description="Authenticated user is not a Product Owner."),
        },
        examples=[
            OpenApiExample(
                "Register product example",
                value={"product_id": "Prod_2", "name": "BetaTrax Mobile", "developers": ["dev-004"]},
                request_only=True,
            ),
            OpenApiExample(
                "Product registered response",
                value={"message": "Product registered successfully", "product_id": "Prod_2"},
                response_only=True,
                status_codes=["201"],
            ),
            OpenApiExample(
                "Register product validation error",
                value={"error": "This Product ID is already in use by another product."},
                response_only=True,
                status_codes=["400"],
            ),
        ],
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
            "Authentication is optional for this endpoint."
        ),
        request=DefectCreateRequestDocSerializer,
        responses={
            201: OpenApiResponse(DefectCreateResponseSerializer, description="Defect submitted."),
            400: OpenApiResponse(MissingFieldsErrorResponseSerializer, description="Required field is missing or blank."),
            404: OpenApiResponse(ErrorResponseSerializer, description="Product ID was not found."),
        },
        examples=[
            OpenApiExample(
                "Submit defect example",
                value={
                    "product_id": "Prod_1",
                    "version": "1.4.0",
                    "title": "Export button fails",
                    "description": "The export button returns a server error.",
                    "steps": "Open reports, click Export.",
                    "tester_id": "tester-104",
                    "email": "tester104@example.com",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Submit defect response",
                value={
                    "report_id": "BT-RP-2477",
                    "status": "New",
                    "required_fields": ["product_id", "version", "title", "description", "steps", "tester_id"],
                },
                response_only=True,
                status_codes=["201"],
            ),
            OpenApiExample(
                "Missing required fields response",
                value={"error": "Missing required fields.", "missing_fields": ["description", "steps"]},
                response_only=True,
                status_codes=["400"],
            ),
        ],
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
        summary="List defects",
        description="List defects by filters. Product Owners and Developers have different visibility scopes.",
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
            OpenApiParameter(
                name="owner_id",
                location=OpenApiParameter.QUERY,
                required=False,
                type=str,
                description="Product Owner username. Must match the authenticated owner.",
            ),
            OpenApiParameter(
                name="developer_id",
                location=OpenApiParameter.QUERY,
                required=False,
                type=str,
                description="Developer username. Must match the authenticated developer.",
            ),
        ],
        responses={
            200: OpenApiResponse(DefectListResponseSerializer, description="Visible defects returned."),
            403: OpenApiResponse(ErrorResponseSerializer, description="User role or filter is not allowed."),
        },
        examples=[
            OpenApiExample(
                "List defects response",
                value={
                    "items": [
                        {
                            "report_id": "BT-RP-2477",
                            "title": "Export button fails",
                            "product_id": "Prod_1",
                            "version": "1.4.0",
                            "tester_id": "tester-104",
                            "status": "Open",
                            "severity": "High",
                            "priority": "P1",
                            "assignee_id": "",
                            "received_at": "2026-04-27T10:30:00+08:00",
                        }
                    ]
                },
                response_only=True,
                status_codes=["200"],
            )
        ],
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

        owner_id = str(request.query_params.get("owner_id", "")).strip()
        if owner_id:
            if not actor.is_owner or owner_id != actor.actor_id:
                return Response({"error": "owner_id must match authenticated Product Owner."}, status=status.HTTP_403_FORBIDDEN)

        developer_id = str(request.query_params.get("developer_id", "")).strip()
        if developer_id:
            if not actor.is_developer or developer_id != actor.actor_id:
                return Response({"error": "developer_id must match authenticated Developer."}, status=status.HTTP_403_FORBIDDEN)

        if actor.is_owner:
            queryset = queryset.filter(product__owner_id=actor.actor_id)
        else:
            queryset = queryset.filter(product__developers__developer_id=actor.actor_id).distinct()

        return Response({"items": [serialize_defect_for_api(defect) for defect in queryset]})


class DefectDetailApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="getDefectDetail",
        summary="Get defect detail",
        description="Retrieve detailed defect information by report_id.",
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
            403: OpenApiResponse(ErrorResponseSerializer, description="User cannot access this defect."),
            404: OpenApiResponse(ErrorResponseSerializer, description="Defect does not exist or is outside the user's scope."),
        },
        examples=[
            OpenApiExample(
                "Defect detail response",
                value={
                    "report_id": "BT-RP-2477",
                    "product_id": "Prod_1",
                    "version": "1.4.0",
                    "title": "Export button fails",
                    "description": "The export button returns a server error.",
                    "steps": "Open reports, click Export.",
                    "tester_id": "tester-104",
                    "email": "tester104@example.com",
                    "status": "Fixed",
                    "severity": "High",
                    "priority": "P1",
                    "assignee_id": "dev-001",
                    "fix_note": "Guarded empty export payloads.",
                    "retest_note": "",
                    "received_at": "2026-04-27T10:30:00+08:00",
                    "decided_at": "2026-04-27T11:15:00+08:00",
                },
                response_only=True,
                status_codes=["200"],
            )
        ],
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
        summary="Apply defect action",
        description=(
            "Apply one lifecycle or comment action to a defect. Supported actions: "
            + ", ".join(DEFECT_ACTION_CHOICES)
            + ". Role and current-status rules are enforced by the API."
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
            403: OpenApiResponse(ErrorResponseSerializer, description="Authenticated user cannot perform the action."),
            404: OpenApiResponse(ErrorResponseSerializer, description="Defect was not found."),
        },
        examples=[
            OpenApiExample(
                "Accept and open",
                value={"action": "accept_open", "severity": "High", "priority": "P1", "backlog_ref": "BL-142"},
                request_only=True,
            ),
            OpenApiExample(
                "Reject",
                value={"action": "reject"},
                request_only=True,
            ),
            OpenApiExample(
                "Mark duplicate",
                value={"action": "duplicate", "duplicate_of": "BT-RP-2471"},
                request_only=True,
            ),
            OpenApiExample(
                "Take ownership",
                value={"action": "take_ownership"},
                request_only=True,
            ),
            OpenApiExample(
                "Set fixed",
                value={"action": "set_fixed", "fix_note": "Patched null export path."},
                request_only=True,
            ),
            OpenApiExample(
                "Cannot reproduce",
                value={"action": "cannot_reproduce", "fix_note": "Unable to reproduce on 1.4.1 after clean install."},
                request_only=True,
            ),
            OpenApiExample(
                "Resolve",
                value={"action": "set_resolved", "retest_note": "Retested successfully on build 1.4.2."},
                request_only=True,
            ),
            OpenApiExample(
                "Reopen",
                value={"action": "reopen", "retest_note": "Regression still occurs with CSV exports."},
                request_only=True,
            ),
            OpenApiExample(
                "Add comment",
                value={"action": "add_comment", "comment": "Need logs from the failed export worker."},
                request_only=True,
            ),
            OpenApiExample(
                "Action response",
                value={"message": "Defect moved to Fixed.", "report_id": "BT-RP-2477", "status": "Fixed"},
                response_only=True,
                status_codes=["200"],
            ),
        ],
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
        summary="Developer effectiveness",
        description=(
            "Only Product Owners can query effectiveness classification for developers in their teams. "
            "Classification uses fixed count and reopened ratio."
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
            403: OpenApiResponse(ErrorResponseSerializer, description="Authenticated user is not a Product Owner."),
        },
        examples=[
            OpenApiExample(
                "Developer effectiveness response",
                value={
                    "developer_id": "dev-001",
                    "fixed": 32,
                    "reopened": 2,
                    "reopen_ratio": 0.0625,
                    "classification": "Fair",
                },
                response_only=True,
                status_codes=["200"],
            )
        ],
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

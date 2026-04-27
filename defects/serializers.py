from rest_framework import serializers

from .services import REQUIRED_CREATE_FIELDS


DEFECT_ACTION_CHOICES = (
    "accept_open",
    "reject",
    "duplicate",
    "take_ownership",
    "set_fixed",
    "cannot_reproduce",
    "set_resolved",
    "reopen",
    "add_comment",
)

DEFECT_STATUS_VALUES = (
    "New",
    "Open",
    "Assigned",
    "Fixed",
    "Resolved",
    "Rejected",
    "Duplicate",
    "Cannot Reproduce",
    "Reopened",
)


class ErrorResponseSerializer(serializers.Serializer):
    error = serializers.JSONField(help_text="String message or serializer error object.")


class MissingFieldsErrorResponseSerializer(serializers.Serializer):
    error = serializers.CharField()
    missing_fields = serializers.ListField(child=serializers.CharField())


class ProductRegisterRequestSerializer(serializers.Serializer):
    product_id = serializers.CharField(max_length=32, help_text="Business product identifier. Must be unique in the current scope.")
    name = serializers.CharField(max_length=128, help_text="Human-readable product name.")
    developers = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        help_text="Optional list of developer usernames to bind to the product.",
    )


class ProductRegisterResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    product_id = serializers.CharField()


class DefectCreateSerializer(serializers.Serializer):
    product_id = serializers.CharField(max_length=32, required=False, allow_blank=True)
    version = serializers.CharField(max_length=64, required=False, allow_blank=True)
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    steps = serializers.CharField(required=False, allow_blank=True)
    tester_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, attrs):
        missing = [name for name in REQUIRED_CREATE_FIELDS if not str(attrs.get(name, "")).strip()]
        if missing:
            raise serializers.ValidationError(
                {"error": "Missing required fields.", "missing_fields": missing}
            )
        return attrs


class DefectCreateRequestDocSerializer(serializers.Serializer):
    product_id = serializers.CharField(max_length=32, help_text="Target product ID. Must already exist.")
    version = serializers.CharField(max_length=64, help_text="Affected product version reported by the tester.")
    title = serializers.CharField(max_length=255, help_text="Short defect summary.")
    description = serializers.CharField(help_text="Detailed defect description.")
    steps = serializers.CharField(help_text="Steps to reproduce.")
    tester_id = serializers.CharField(max_length=64, help_text="External tester identifier.")
    email = serializers.EmailField(required=False, allow_blank=True, help_text="Optional tester email for notifications.")


class DefectCreateResponseSerializer(serializers.Serializer):
    report_id = serializers.CharField()
    status = serializers.ChoiceField(choices=DEFECT_STATUS_VALUES)
    required_fields = serializers.ListField(child=serializers.CharField())


class DefectListItemSerializer(serializers.Serializer):
    report_id = serializers.CharField()
    title = serializers.CharField()
    product_id = serializers.CharField()
    version = serializers.CharField()
    tester_id = serializers.CharField()
    status = serializers.ChoiceField(choices=DEFECT_STATUS_VALUES)
    severity = serializers.CharField(allow_blank=True)
    priority = serializers.CharField(allow_blank=True)
    assignee_id = serializers.CharField(allow_blank=True)
    received_at = serializers.DateTimeField()


class DefectListResponseSerializer(serializers.Serializer):
    items = DefectListItemSerializer(many=True)


class DefectDetailResponseSerializer(serializers.Serializer):
    report_id = serializers.CharField()
    product_id = serializers.CharField()
    version = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    steps = serializers.CharField()
    tester_id = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    status = serializers.ChoiceField(choices=DEFECT_STATUS_VALUES)
    severity = serializers.CharField(allow_blank=True)
    priority = serializers.CharField(allow_blank=True)
    assignee_id = serializers.CharField(allow_blank=True)
    fix_note = serializers.CharField(allow_blank=True)
    retest_note = serializers.CharField(allow_blank=True)
    received_at = serializers.DateTimeField()
    decided_at = serializers.DateTimeField(allow_null=True)


class DefectActionSerializer(serializers.Serializer):
    action = serializers.CharField(
        max_length=64,
        help_text="One of: " + ", ".join(DEFECT_ACTION_CHOICES),
    )
    owner_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
    developer_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
    severity = serializers.CharField(max_length=16, required=False, allow_blank=True)
    priority = serializers.CharField(max_length=8, required=False, allow_blank=True)
    backlog_ref = serializers.CharField(max_length=64, required=False, allow_blank=True)
    duplicate_of = serializers.CharField(max_length=32, required=False, allow_blank=True)
    fix_note = serializers.CharField(required=False, allow_blank=True)
    retest_note = serializers.CharField(required=False, allow_blank=True)
    author = serializers.CharField(max_length=64, required=False, allow_blank=True)
    comment = serializers.CharField(required=False, allow_blank=True)


class DefectActionRequestDocSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=DEFECT_ACTION_CHOICES,
        help_text="Workflow action to apply. Field requirements depend on the selected action.",
    )
    severity = serializers.ChoiceField(
        choices=("High", "Medium", "Low"),
        required=False,
        help_text="Required for accept_open.",
    )
    priority = serializers.ChoiceField(
        choices=("P1", "P2", "P3"),
        required=False,
        help_text="Required for accept_open.",
    )
    backlog_ref = serializers.CharField(
        max_length=64,
        required=False,
        allow_blank=True,
        help_text="Optional backlog or tracking reference used with accept_open.",
    )
    duplicate_of = serializers.CharField(
        max_length=32,
        required=False,
        allow_blank=True,
        help_text="Required for duplicate. Root defect report ID to link against.",
    )
    fix_note = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional implementation or investigation note for set_fixed and cannot_reproduce.",
    )
    retest_note = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Retest note used with set_resolved and reopen. Reopen requires a non-empty note.",
    )
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Comment body for add_comment. Must not be blank when add_comment is used.",
    )


class DefectActionResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    report_id = serializers.CharField()
    status = serializers.ChoiceField(choices=DEFECT_STATUS_VALUES)


class DeveloperEffectivenessResponseSerializer(serializers.Serializer):
    developer_id = serializers.CharField()
    fixed = serializers.IntegerField(min_value=0)
    reopened = serializers.IntegerField(min_value=0)
    reopen_ratio = serializers.FloatField(allow_null=True)
    classification = serializers.ChoiceField(
        choices=("Insufficient data", "Good", "Fair", "Poor")
    )

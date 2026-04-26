from rest_framework import serializers

from .services import REQUIRED_CREATE_FIELDS


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


class DefectActionSerializer(serializers.Serializer):
    action = serializers.CharField(max_length=64)
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

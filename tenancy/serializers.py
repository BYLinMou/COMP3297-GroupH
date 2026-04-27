from rest_framework import serializers


class TenantRegisterSerializer(serializers.Serializer):
    schema_name = serializers.CharField(
        max_length=63,
        help_text="Tenant schema name. Use lowercase letters, digits, and underscores, starting with a letter.",
    )
    domain = serializers.CharField(
        max_length=255,
        help_text="Primary domain mapped to the tenant.",
    )
    name = serializers.CharField(
        max_length=128,
        required=False,
        allow_blank=True,
        help_text="Optional display name for the tenant.",
    )


class TenantInfoSerializer(serializers.Serializer):
    schema_name = serializers.CharField(max_length=63)
    domain = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=128, allow_blank=True)
    is_active = serializers.BooleanField()


class TenantRegisterResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    tenant = TenantInfoSerializer()

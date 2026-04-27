from rest_framework import serializers


class TenantRegisterSerializer(serializers.Serializer):
    schema_name = serializers.CharField(max_length=63)
    domain = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=128, required=False, allow_blank=True)


class TenantInfoSerializer(serializers.Serializer):
    schema_name = serializers.CharField(max_length=63)
    domain = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=128, allow_blank=True)
    is_active = serializers.BooleanField()


class TenantRegisterResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    tenant = TenantInfoSerializer()

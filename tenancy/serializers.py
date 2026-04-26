from rest_framework import serializers


class TenantRegisterSerializer(serializers.Serializer):
    schema_name = serializers.CharField(max_length=63)
    domain = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=128, required=False, allow_blank=True)

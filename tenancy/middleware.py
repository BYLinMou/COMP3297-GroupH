from django.conf import settings

try:
    from django_tenants.middleware.main import TenantMainMiddleware
except Exception:  # pragma: no cover - django-tenants is optional outside tenant mode
    TenantMainMiddleware = object  # type: ignore[misc,assignment]


class PublicDomainTenantMiddleware(TenantMainMiddleware):
    def no_tenant_found(self, request, hostname):
        public_domains = set(getattr(settings, "PUBLIC_SCHEMA_DOMAINS", []))
        if public_domains:
            if hostname in public_domains:
                self.setup_url_routing(request=request, force_public=True)
                return None
            raise self.TENANT_NOT_FOUND_EXCEPTION('No tenant for hostname "%s"' % hostname)
        return super().no_tenant_found(request, hostname)

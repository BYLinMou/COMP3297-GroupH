"""Single-schema test suite entrypoint for CI.

This module groups tests that are expected to execute with
ENABLE_DJANGO_TENANTS=False. Tenant-mode integration tests are run by
betatrax.suite_tenant_mode instead.
"""

from betatrax.test_api_schema import *  # noqa: F401,F403
from betatrax.tests import *  # noqa: F401,F403
from defects.tests import *  # noqa: F401,F403
from frontend.tests import *  # noqa: F401,F403
from tenancy.tests import *  # noqa: F401,F403

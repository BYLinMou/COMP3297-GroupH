"""Compatibility test module for CI jobs that import defects.tests directly."""

from defects.testsuite.test_api_client import *  # noqa: F401,F403
from defects.testsuite.test_services import *  # noqa: F401,F403
from defects.testsuite.test_views_request_factory import *  # noqa: F401,F403

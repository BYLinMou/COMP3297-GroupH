# Automated Testing Baseline

This project now uses Django's built-in test runner together with Django REST Framework test utilities and `coverage.py`.

## Test layers

- `defects/tests/test_api_client.py`: endpoint-level integration tests using `APITestCase` and `APIClient`
- `defects/tests/test_views_request_factory.py`: direct view tests using `APIRequestFactory`
- `defects/tests/test_services.py`: unit-style service tests for transition logic and product registration rules
- `frontend/tests.py`: smoke tests for key HTML flows

## Shared fixtures

`defects/tests/base.py` provides reusable setup for:

- owner and developer accounts
- a seeded product and developer assignment
- a seeded defect report
- helper methods for authenticated API GET/POST requests
- lifecycle shortcuts for moving a defect to `Open`, `Assigned`, and `Fixed`

Add new Sprint 3 endpoint tests by extending `DefectApiTestCase` instead of duplicating setup.

## Commands

Run all tests:

```powershell
python manage.py test
```

Run tests with branch coverage:

```powershell
coverage run --branch manage.py test
coverage report
coverage html
```

The HTML report is generated at `htmlcov/index.html`.

## Conventions for next features

- Add at least one representative endpoint test for every new API action
- Add focused service-level tests for branch-heavy logic
- Prefer `APITestCase` for endpoint flows and `APIRequestFactory` for direct view assertions
- Keep reusable fixtures in `defects/tests/base.py`

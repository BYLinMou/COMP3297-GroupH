# Automated Testing Baseline

This project now uses Django's built-in test runner together with Django REST Framework test utilities and `coverage.py`.

For the concrete test case inventory (what each test file covers), refer to `documents/testcase.md`.

## CI workflow

The GitHub Actions CI workflow in `.github/workflows/ci.yml` currently performs these checks:

Non-tenant SQLite job:

- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py test defects.testsuite.test_services frontend.tests --verbosity 2`
- `python manage.py test defects.testsuite.test_api_client --verbosity 2`
- `python manage.py test defects.testsuite.test_views_request_factory --verbosity 2`
- `python manage.py test defects.testsuite.test_effectiveness --verbosity 2`
- `python manage.py test defects.tests --verbosity 2`
- `python -m coverage run --branch --omit=*/migrations/*,tenancy/test_tenant_mode_integration.py,betatrax/suite_tenant_mode.py,manage.py,*/asgi.py,*/wsgi.py manage.py test betatrax.suite_single_schema --verbosity 2`
- `python -m coverage report --fail-under=100`
- `python -m coverage xml -o coverage.xml`
- `python -m coverage html`

Tenant-mode PostgreSQL job:

- Starts a PostgreSQL service container
- Sets `ENABLE_DJANGO_TENANTS=True`
- Uses `django_tenants.postgresql_backend`
- Runs `python manage.py check`
- Runs `python -m coverage run --branch --source=tenancy --omit=*/migrations/*,tenancy/tests.py,manage.py,*/asgi.py,*/wsgi.py manage.py test betatrax.suite_tenant_mode --verbosity 2`
- Runs `python -m coverage report --fail-under=100`
- Exports `tenant-coverage.xml` and `tenant-htmlcov/`

CI uploads `coverage.xml` and `htmlcov/` as the `coverage-report` artifact.
Tenant-mode coverage is uploaded separately as the `tenant-coverage-report` artifact.

## Test layers

- `defects/tests.py`: compatibility entrypoint that re-exports the Sprint 3 defect test suite for CI and explicit test labels
- `defects/testsuite/test_api_client.py`: endpoint-level integration tests using `APITestCase` and `APIClient`
- `defects/testsuite/test_views_request_factory.py`: direct view tests using `APIRequestFactory`
- `defects/testsuite/test_services.py`: unit-style service tests for transition logic, registration rules, and tenant public-schema seed guards
- `defects/testsuite/test_effectiveness.py`: branch-focused tests for `classify_developer(fixed, reopened)`
- `betatrax/test_api_schema.py`: OpenAPI schema regression tests for documented operation IDs, response schemas, and defect action enums
- `tenancy/test_tenant_mode_integration.py`: tenant-mode integration tests that create a PostgreSQL tenant schema, verify tenant-scoped defect API access, and verify public-schema tenant registration
- `frontend/tests.py`: smoke tests for key HTML flows

## Shared fixtures

`defects/testsuite/base.py` provides reusable setup for:

- owner and developer accounts
- a seeded product and developer assignment
- a seeded defect report
- helper methods for authenticated API GET/POST requests
- lifecycle shortcuts for moving a defect to `Open`, `Assigned`, and `Fixed`

Add new Sprint 3 endpoint tests by extending `DefectApiTestCase` instead of duplicating setup.

## Commands

Run the single-schema suite:

```powershell
python manage.py test betatrax.suite_single_schema --verbosity 2
```

Run unit/service and frontend tests explicitly:

```powershell
python manage.py test defects.testsuite.test_services frontend.tests --verbosity 2
```

Run endpoint tests with DRF `APIClient`:

```powershell
python manage.py test defects.testsuite.test_api_client --verbosity 2
```

Run direct view tests with DRF `APIRequestFactory`:

```powershell
python manage.py test defects.testsuite.test_views_request_factory --verbosity 2
```

Run effectiveness classification tests only:

```powershell
python manage.py test defects.testsuite.test_effectiveness --verbosity 2
```

Run the explicit compatibility entrypoint:

```powershell
python manage.py test defects.tests --verbosity 2
```

Run tests with branch coverage:

```powershell
python -m coverage run --branch --omit=*/migrations/*,tenancy/test_tenant_mode_integration.py,betatrax/suite_tenant_mode.py,manage.py,*/asgi.py,*/wsgi.py manage.py test betatrax.suite_single_schema --verbosity 2
python -m coverage report --fail-under=100
python -m coverage xml -o coverage.xml
python -m coverage html
```

Run the tenant-mode integration suite against PostgreSQL:

```powershell
$env:ENABLE_DJANGO_TENANTS='True'
$env:DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/betatrax'
python -m coverage run --branch --source=tenancy --omit=*/migrations/*,tenancy/tests.py,manage.py,*/asgi.py,*/wsgi.py manage.py test betatrax.suite_tenant_mode --verbosity 2
python -m coverage report --fail-under=100
python -m coverage xml -o tenant-coverage.xml
python -m coverage html -d tenant-htmlcov
```

CI separates suite entrypoints by execution mode: `betatrax.suite_single_schema`
runs the SQLite/non-tenant tests, and `betatrax.suite_tenant_mode` runs the
PostgreSQL tenant integration tests. Together they cover all test files without
discovering mode-incompatible tests in either job.

Run a tenant-mode configuration check against PostgreSQL:

```powershell
$env:ENABLE_DJANGO_TENANTS='True'
$env:DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/betatrax'
python manage.py check
python manage.py migrate_schemas --shared --noinput
```

Run focused branch+statement coverage for classification module:

```powershell
python -m coverage run --branch manage.py test defects.testsuite.test_effectiveness --verbosity 2
python -m coverage report -m --include="defects/effectiveness.py"
```

Generated reports:

- console summary from `coverage report`
- XML report at `coverage.xml`
- HTML report at `htmlcov/index.html`
- tenant XML report at `tenant-coverage.xml`
- tenant HTML report at `tenant-htmlcov/index.html`

Coverage is configured through `.coveragerc`.
Application code is included in coverage; migration files and test modules are intentionally omitted.

## Conventions for next features

- Add at least one representative endpoint test for every new API action
- Add focused service-level tests for branch-heavy logic
- Prefer `APITestCase` for endpoint flows and `APIRequestFactory` for direct view assertions
- Keep reusable fixtures in `defects/testsuite/base.py`
- Preserve `defects/tests.py` as a stable compatibility entrypoint when reorganizing the defect test suite
- Use `if ... else ...` instead of a logically unreachable `elif` branch when earlier guards already guarantee only two valid actor paths, otherwise branch coverage may report a false gap

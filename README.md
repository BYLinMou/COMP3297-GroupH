# BetaTrax

BetaTrax is a lightweight defect tracking system built for the COMP3297 software engineering project.
It supports the core bug lifecycle from **New -> Open -> Assigned -> Fixed -> Resolved**.
The current implementation is built on a Django-based architecture (see the `betatrax/` project module).

## Demo Website

- Demo website: [betatrax.zeabur.app](https://betatrax.zeabur.app)
- Demo website 2 (backup): [betatrax.yeelam.site](https://betatrax.yeelam.site)
- Admin account: `user`
- Admin password: `testtest`
- We recommend using the demo website first because SMTP is already configured there and it is easier to use for evaluation.

## Workflows

This repository currently uses three GitHub Actions workflows:

1. **CI check** (`.github/workflows/ci.yml`)
Runs on every push and pull request to validate functionality with:
- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py test defects.testsuite.test_services frontend.tests --verbosity 2`
- `python manage.py test defects.testsuite.test_api_client --verbosity 2`
- `python manage.py test defects.testsuite.test_views_request_factory --verbosity 2`
- `python manage.py test --verbosity 2`
- `python manage.py test defects.tests --verbosity 2`
- `python -m coverage run --branch manage.py test`
- `python -m coverage report`
- `python -m coverage xml -o coverage.xml`
- `python -m coverage html`

The CI workflow uploads `coverage.xml` and `htmlcov/` as a `coverage-report` artifact.
This is the current Sprint 3 automated testing baseline.

2. **Auto Release** (`.github/workflows/auto-release.yml`)
Creates a GitHub Release after CI succeeds on `main`.
It can also be triggered manually for alpha/beta releases.
Release version is read from the `VERSION` file by default, or overridden via manual input.

3. **Container Image** (`.github/workflows/container-image.yml`)
Builds and pushes a Docker image to GitHub Container Registry (GHCR) only after CI succeeds on `main`.
It can also be triggered manually with an optional `image_tag` input (for example, `alpha`).
By default, image version tag is read from the `VERSION` file. Automatic runs also update `latest`.
The published image path is `ghcr.io/<owner>/<repo>`.

## Docker Deployment
We recommend using Docker container setup for an isolated and consistent environment.

Use the published image:

```bash
docker pull ghcr.io/bylinmou/comp3297-grouph:latest
```

Recommended host layout (keep SQLite DB out of repo root):

```bash
mkdir -p data
cp .env.example .env
```

Run container with DB file mount:

```bash
docker run --name betatrax \
  -p 8000:8000 \
  --env-file .env \
  -v "$(pwd)/data:/data" \
  ghcr.io/bylinmou/comp3297-grouph:latest
```

PowerShell equivalent:

```powershell
docker run --name betatrax `
  -p 8000:8000 `
  --env-file .env `
  -v "${PWD}\\data:/data" `
  ghcr.io/bylinmou/comp3297-grouph:latest
```

Then open `http://127.0.0.1:8000/`.

On startup, the container waits for the configured database and applies
migrations automatically. With `ENABLE_DJANGO_TENANTS=True`, it runs:

```bash
python manage.py migrate_schemas --shared --noinput
```

Otherwise it runs:

```bash
python manage.py migrate --noinput
```

Set `AUTO_MIGRATE=False` only if migrations are handled outside the container.

## Local Development

```bash
# Create and activate conda environment
conda create -n betatrax python=3.12
conda activate betatrax

# Install dependencies
pip install -r requirements.txt

# Copy environment config (edit as needed)
cp .env.example .env

# Set SQLITE_PATH=./data/db.sqlite3 in .env
(Get-Content .env) -replace '^SQLITE_PATH=.*$', 'SQLITE_PATH=./data/db.sqlite3' | Set-Content .env
mkdir data

# Apply database migrations
python manage.py migrate

# Start the development server
python manage.py runserver
```

The app will be available at `http://127.0.0.1:8000/`.

### PostgreSQL + Tenant Ready Config (Sprint 3)

Sprint 3 adds PostgreSQL-ready configuration and tenant registration API.

Set these variables in `.env` when using PostgreSQL:

- `DATABASE_ENGINE=postgresql`
- `POSTGRES_DB=betatrax`
- `POSTGRES_USER=postgres`
- `POSTGRES_PASSWORD=postgres`
- `POSTGRES_HOST=127.0.0.1`
- `POSTGRES_PORT=5432`

Optional tenant middleware wiring can be enabled with:

- `ENABLE_DJANGO_TENANTS=True`

When tenant mode is enabled, BetaTrax configures `SHARED_APPS`, `TENANT_APPS`,
`TENANT_MODEL=tenancy.Tenant`, `TENANT_DOMAIN_MODEL=tenancy.Domain`, and the
`django_tenants.postgresql_backend` database backend. The `tenancy` app stores
company/tenant registry data in the public schema, while `defects` stores
tenant-scoped product and defect data inside each company schema. In Docker, shared
migrations are applied automatically by the entrypoint. For manual local setup,
run:

```bash
python manage.py migrate_schemas --shared
```

By default, this flag is disabled to keep local/CI setup simple. Use normal
`python manage.py migrate` when `ENABLE_DJANGO_TENANTS=False` and you are not
starting through Docker.

When `SHOW_PUBLIC_IF_NO_TENANT_FOUND=True`, allowed hosts that do not match a
tenant domain use the public schema URL set. Public routes expose tenant
registration/admin only; product and defect routes are tenant-scoped.

## Automated Testing

Sprint 3 testing now uses Django's built-in test runner, Django REST Framework test utilities, and `coverage.py`.

### Test layout

- `defects/tests.py`
  Compatibility entrypoint for CI jobs or local commands that explicitly run `python manage.py test defects.tests`
- `defects/testsuite/test_api_client.py`
  Endpoint-level integration tests using `APITestCase` and DRF's `APIClient`
- `defects/testsuite/test_views_request_factory.py`
  Direct view tests using `APIRequestFactory`
- `defects/testsuite/test_services.py`
  Service-layer tests for status transition and registration logic
- `defects/testsuite/test_effectiveness.py`
  Branch/statement coverage tests for developer effectiveness classification rules
- `frontend/tests.py`
  Smoke tests for key HTML flows

### Local commands

Run the full discovered suite:

```bash
python manage.py test --verbosity 2
```

Run the unit/frontend layer explicitly:

```bash
python manage.py test defects.testsuite.test_services frontend.tests --verbosity 2
```

Run endpoint tests with DRF `APIClient`:

```bash
python manage.py test defects.testsuite.test_api_client --verbosity 2
```

Run direct view tests with `APIRequestFactory`:

```bash
python manage.py test defects.testsuite.test_views_request_factory --verbosity 2
```

Run effectiveness classification tests explicitly:

```bash
python manage.py test defects.testsuite.test_effectiveness --verbosity 2
```

Run the compatibility entrypoint explicitly:

```bash
python manage.py test defects.tests --verbosity 2
```

Run branch coverage and generate reports:

```bash
python -m coverage run --branch manage.py test
python -m coverage report
python -m coverage xml -o coverage.xml
python -m coverage html
```

Coverage configuration is stored in `.coveragerc`.
Generated artifacts are:

- `coverage.xml`
- `htmlcov/index.html`

For implementation details and conventions, see [documents/automated-testing.md](documents/automated-testing.md).

## API (Sprint 2)

Testing commands are provided in [testcasecommand.txt](documents/testcasecommand.txt) (using demo website 2).

### 0) Register product

- Method: `POST`
- Path: `/api/products/register/`
- Auth: required (`Session` or `Basic`)
- Role: Product Owner only

Request example:

```json
{
  "product_id": "Prod_2",
  "name": "BetaTrax Mobile",
  "developers": ["dev-004"]
}
```

Responses:
- `201` created (returns `product_id`)
- `400` validation failure (duplicate product, owner already has a product, invalid developer, etc.)
- `403` non-owner account

## API (Sprint 3)

### 1) Register tenant

- Method: `POST`
- Path: `/api/tenants/register/`
- Auth: required (`Session` or `Basic`)
- Role: Platform Admin only (superuser or `platform_admin` group)

Request example:

```json
{
  "schema_name": "team_a",
  "domain": "team-a.example.com",
  "name": "Team A"
}
```

Responses:
- `201` created
- `400` validation failure
- `403` non-platform-admin account

In tenant mode, successful registration creates the tenant row, a primary
`Domain` row in the public schema, and the PostgreSQL schema for that tenant.

### 2) Developer effectiveness metric

- Method: `GET`
- Path: `/api/developers/{developer_id}/effectiveness/`
- Auth: required (`Session` or `Basic`)
- Role: Product Owner only

Response example:

```json
{
  "developer_id": "dev-001",
  "fixed": 36,
  "reopened": 2,
  "reopen_ratio": 0.05555555555555555,
  "classification": "Fair"
}
```

Classification rules:
- `fixed < 20` -> `Insufficient data`
- `reopened / fixed < 1/32` -> `Good`
- `1/32 <= reopened / fixed < 1/8` -> `Fair`
- `reopened / fixed >= 1/8` -> `Poor`

### 3) Duplicate chain email notification

When the root defect of a duplicate chain changes status, the system now:

- Finds all linked duplicate reports recursively
- Sends notification emails to testers of linked duplicates (only when those reports store tester email)

### 4) API documentation

When `drf-spectacular` is available, generated API docs are exposed at:

- OpenAPI schema: `/api/schema/`
- Swagger UI: `/api/docs/`

## API (Sprint 1)

Base path: `/api/defects/`

Testing commands are provided in [testcasecommand.txt](documents/testcasecommand.txt) (using demo website 2).

Sprint 1 acceptance criteria are provided in [Sprint1_Demo_API.ipynb](documents/Sprint1_Demo_API.ipynb) (using demo website 2).

### 1) Create defect report

- Method: `POST`
- Path: `/api/defects/new/`
- Content-Type: `application/json`
- Auth: not required (external system endpoint)
- Required fields:
  - `product_id`, `version`, `title`, `description`, `steps`, `tester_id`
- Optional fields:
  - `email`

Request example:

```json
{
  "product_id": "Prod_1",
  "version": "0.9.0",
  "title": "Poor readability in dark mode",
  "description": "Text unclear in dark mode due to lack of contrast with background",
  "steps": "1) Enable dark mode 2) Display text",
  "tester_id": "Tester_2",
  "email": "tester@example.com"
}
```

Responses:
- `201` created (returns `report_id`, `status`)
- `400` missing/invalid fields
- `404` unknown `product_id`

### 2) List defects

- Method: `GET`
- Path: `/api/defects/`
- Auth: required (`Session` or `Basic`)
- Query params (all optional):
  - `status` (for example `New`, `Open`, `Assigned`, `Fixed`, `Resolved`)
  - `product_id`
  - `owner_id` (must match logged-in Product Owner username)
  - `developer_id` (must match logged-in Developer username)

Response `200`:

```json
{
  "items": [
    {
      "report_id": "BT-RP-1002",
      "title": "Poor readability in dark mode",
      "product_id": "Prod_1",
      "version": "0.9.0",
      "tester_id": "Tester_2",
      "status": "New",
      "severity": "",
      "priority": "",
      "assignee_id": "",
      "received_at": "2026-03-25T20:17:00+08:00"
    }
  ]
}
```

### 3) Defect actions (status transitions / comment)

- Method: `POST`
- Path: `/api/defects/<defect_id>/actions/`
- Content-Type: `application/json`
- Auth: required (`Session` or `Basic`)
- Required field:
  - `action`

Supported `action` values:
- `accept_open`
- `reject`
- `duplicate`
- `take_ownership`
- `set_fixed`
- `cannot_reproduce`
- `set_resolved`
- `reopen`
- `add_comment`

Action-specific fields:
- `accept_open`: `severity` (`High|Medium|Low`), `priority` (`P1|P2|P3`), `backlog_ref` (optional)
- `reject`: no additional field
- `duplicate`: `duplicate_of` (optional)
- `take_ownership`: no additional field (assignee is current user)
- `set_fixed`: `fix_note` (optional)
- `cannot_reproduce`: `fix_note` (optional)
- `set_resolved`: `retest_note` (optional)
- `reopen`: `retest_note` (optional)
- `add_comment`: `comment` (author is current user)

Response `200`:

```json
{
  "message": "Defect moved to Fixed.",
  "report_id": "BT-RP-1001",
  "status": "Fixed"
}
```

Error responses:
- `400` invalid transition, invalid role/user, or validation error
- `404` defect not found
- `403` unauthenticated or unauthorized access

## Demo Accounts (Auto-created)

The system auto-creates Sprint 1 demo users and roles:

- Product Owner: `owner-001`
- Developers: `dev-001`, `dev-004`
- Password (all): `Pass1234!`

Use `/auth/` for sign in, then access owner/developer screens.

## Initial Demo Data (Auto-seeded)

After running `python manage.py migrate`, the app seeds initial data on first use
(for example when opening `/`, `/auth/`, or any defects API endpoint).

Seeded records include:

- Roles: `owner`, `developer`
- Product:
  - `Prod_1` (name: `BetaTrax Demo Product`, owner: `owner-001`)
- Product developers:
  - `dev-001`
  - Demo team account kept separately: `dev-004` (not linked to `Prod_1`)
- Defect reports (inserted only when `Prod_1` has no defect reports yet):
  - `BT-RP-1001` (`Assigned`) - `Unable to search`
  - `BT-RP-1002` (`New`) - `Poor readability in dark mode`

Notes:

- If there is already at least one defect report, seeded defect reports are not added again.
- The seed helper is idempotent for roles, users, product, and team membership.

### SMTP setup (Google)

Email is disabled by default (`EMAIL_ENABLED=False`) to keep Sprint 1 flow simple.
If you want to enable notification emails, configure these in `.env`:

- `EMAIL_ENABLED=True`
- `EMAIL_HOST=smtp.gmail.com`
- `EMAIL_PORT=587`
- `EMAIL_USE_TLS=True`
- `EMAIL_HOST_USER=<your-gmail-address>`
- `EMAIL_HOST_PASSWORD=<google-app-password>`
- `DEFAULT_FROM_EMAIL=BetaTrax <your-gmail-address>`

For Google accounts, use a Google App Password (16 characters) instead of your login password.

## Sprint 1 Limitations

The following limitations are present in this Sprint 1 executable:

1. User registration is not implemented in API/UI.
  Users are created through Django Admin as per course instruction.

2. Product registration is available for Product Owner accounts via API and UI (`/products/register/`).
  Sprint 1 demo data still defaults to a single seeded product (`Prod_1`).

3. The executable is prepared for Sprint 1 with a single demo product (`Prod_1`).
    Multi-product support exists in data model, but full multi-product admin workflows are not part of Sprint 1 scope.

4. Email notifications:
    - When `EMAIL_ENABLED=True`, notifications are sent via SMTP.
    - When `EMAIL_ENABLED=False`, emails are printed to console for demo/testing.
    - Real mailbox delivery depends on external SMTP configuration.

5. Authentication/authorization is role-based using pre-created demo accounts.
    No self-service signup/password reset is provided (Only available through admin console).

6. UI is a Sprint 1 MVP and does not cover all future lifecycle paths from full use-case set.

## License

This project is licensed under **GNU General Public License v3.0 (GPL-3.0)**.
See the [LICENSE](LICENSE) file for details.

## Contribution Rule

1. Create a feature branch for each task.
2. Keep pull requests small and focused.
3. Add or update tests for behavior changes.
4. Get at least one teammate review before merging.

# BetaTrax System Architecture

This document describes the current BetaTrax codebase architecture, based on the repository files in this project.

## Overview

BetaTrax is a Django defect tracking system with two user-facing surfaces:

- Server-rendered web UI in the `frontend` Django app
- JSON API in the `defects` Django app using Django REST Framework

Both surfaces use the same backend service layer in `defects/services.py`. This is the main architectural boundary: views handle HTTP, serializers validate API payload shape, and services enforce business rules and mutate models.

The project also includes optional PostgreSQL schema-based multi-tenancy through `django-tenants`.

## Repository Tree

```text
COMP3297-GroupH/
+-- .github/
|   +-- workflows/
|       +-- auto-release.yml
|       +-- ci.yml
|       +-- container-image.yml
+-- betatrax/
|   +-- __init__.py
|   +-- asgi.py
|   +-- public_urls.py
|   +-- settings.py
|   +-- urls.py
|   +-- wsgi.py
+-- defects/
|   +-- migrations/
|   |   +-- 0001_initial.py
|   |   +-- 0002_tenant_model.py
|   |   +-- 0003_alter_tenant_schema_name_domain.py
|   |   +-- 0004_delete_domain_delete_tenant.py
|   |   +-- __init__.py
|   +-- testsuite/
|   |   +-- __init__.py
|   |   +-- base.py
|   |   +-- test_api_client.py
|   |   +-- test_effectiveness.py
|   |   +-- test_services.py
|   |   +-- test_views_request_factory.py
|   +-- __init__.py
|   +-- admin.py
|   +-- apps.py
|   +-- authz.py
|   +-- effectiveness.py
|   +-- models.py
|   +-- serializers.py
|   +-- services.py
|   +-- signals.py
|   +-- tests.py
|   +-- urls.py
|   +-- views.py
+-- documents/
|   +-- automated-testing.md
|   +-- Sprint1_Demo_API.ipynb
|   +-- tenant-usage.md
|   +-- testcasecommand.txt
|   +-- system-architecture.md
+-- frontend/
|   +-- migrations/
|   |   +-- 0001_initial.py
|   |   +-- __init__.py
|   +-- static/
|   |   +-- frontend/
|   |       +-- app.js
|   |       +-- styles.css
|   +-- templates/
|   |   +-- frontend/
|   |       +-- auth.html
|   |       +-- base.html
|   |       +-- defect_detail.html
|   |       +-- home.html
|   |       +-- new_defect.html
|   |       +-- register_product.html
|   +-- __init__.py
|   +-- admin.py
|   +-- apps.py
|   +-- models.py
|   +-- tests.py
|   +-- urls.py
|   +-- views.py
+-- tenancy/
|   +-- migrations/
|   |   +-- 0001_initial.py
|   |   +-- __init__.py
|   +-- __init__.py
|   +-- admin.py
|   +-- apps.py
|   +-- middleware.py
|   +-- models.py
|   +-- serializers.py
|   +-- services.py
|   +-- static/
|   |   +-- tenancy/
|   |       +-- platform.css
|   +-- templates/
|   |   +-- tenancy/
|   |       +-- platform_login.html
|   |       +-- tenant_console.html
|   +-- tests.py
|   +-- utils.py
|   +-- views.py
+-- .coveragerc
+-- .dockerignore
+-- .env.example
+-- .gitignore
+-- AGENTS.md
+-- Dockerfile
+-- docker-entrypoint.sh
+-- LICENSE
+-- manage.py
+-- README.md
+-- requirements.txt
+-- VERSION
```

Ignored/generated local folders such as `.conda/`, `data/`, `htmlcov/`, `__pycache__/`, and `.coverage` are not part of the intended application source.

## Runtime Stack

| Area | Technology |
| --- | --- |
| Web framework | Django 5.2 |
| API framework | Django REST Framework |
| API documentation | drf-spectacular, optional |
| Multi-tenancy | django-tenants, optional |
| Database | SQLite by default, PostgreSQL for tenant mode |
| Email | Django email backend, console by default or SMTP when enabled |
| Frontend | Django templates, static CSS, small vanilla JS helpers |
| Container | `python:3.12-slim` Docker image |
| CI | GitHub Actions |

## High-Level Component Diagram

```mermaid
flowchart LR
    Browser[Browser / API Client]
    URLs[betatrax.urls]
    Frontend[frontend views + templates]
    API[defects API views]
    Tenancy[tenancy platform API]
    Serializers[DRF serializers]
    Services[defects.services]
    Authz[defects.authz]
    Models[defects.models]
    DB[(SQLite or PostgreSQL)]
    Email[Django email backend]

    Browser --> URLs
    URLs --> Frontend
    URLs --> API
    URLs --> Tenancy
    API --> Serializers
    API --> Authz
    Frontend --> Authz
    API --> Services
    Frontend --> Services
    Services --> Models
    Models --> DB
    Services --> Email
```

## Django Project Layer

### `betatrax/settings.py`

Main runtime configuration:

- Loads `.env` manually at startup.
- Configures `INSTALLED_APPS`, middleware, database, static files, DRF, drf-spectacular, email.
- Supports normal mode and tenant mode.
- Normal mode:
  - `DATABASE_URL=sqlite:///./data/db.sqlite3` uses SQLite.
  - `DATABASE_URL=postgresql://user:password@host:5432/dbname` uses normal Django PostgreSQL backend.
- Tenant mode:
  - `ENABLE_DJANGO_TENANTS=True`
  - requires a PostgreSQL `DATABASE_URL`
  - inserts `django_tenants.middleware.main.TenantMainMiddleware`
  - defines `SHARED_APPS`, `TENANT_APPS`, `TENANT_MODEL`, `TENANT_DOMAIN_MODEL`
  - switches engine to `django_tenants.postgresql_backend`
  - uses `django_tenants.routers.TenantSyncRouter`

### `betatrax/urls.py`

Tenant URL routing:

| Path | Target |
| --- | --- |
| `/admin/` | Django admin |
| `/api/defects/` | `defects.urls` |
| `/api/products/register/` | `ProductRegisterApi` |
| `/api/tenants/register/` | `TenantRegisterApi` |
| `/api/developers/<developer_id>/effectiveness/` | `DeveloperEffectivenessApi` |
| `/api/schema/` | OpenAPI schema when drf-spectacular is installed |
| `/api/docs/` | Swagger UI when drf-spectacular is installed |
| `/` and frontend paths | `frontend.urls` |

### `betatrax/public_urls.py`

Public schema URL routing when tenant mode is enabled:

| Path | Target |
| --- | --- |
| `/` | Redirects to `/platform/tenants/` |
| `/platform/login/` | Platform tenant console login |
| `/platform/logout/` | Platform tenant console logout |
| `/admin/` | Django admin for shared/platform models |
| `/platform/tenants/` | Platform tenant console |
| `/api/tenants/register/` | `TenantRegisterApi` |
| `/api/schema/` | OpenAPI schema when drf-spectacular is installed |
| `/api/docs/` | Swagger UI when drf-spectacular is installed |

## Backend App: `defects`

The `defects` app is the core domain layer.

### File Responsibilities

| File | Responsibility |
| --- | --- |
| `models.py` | Database schema and domain model definitions |
| `services.py` | Business rules, lifecycle transitions, notification logic, registration logic |
| `views.py` | DRF API controllers |
| `serializers.py` | Request validation for API payloads |
| `authz.py` | Role extraction from Django users/groups |
| `effectiveness.py` | Developer effectiveness classification function |
| `urls.py` | Defect API URL routes |
| `signals.py` | Runs demo seed helper after migrations when defect tables exist; skips tenant public-schema migrations |
| `admin.py` | Django admin registration |
| `testsuite/` | API, service, view-factory, and effectiveness tests |
| `tests.py` | Compatibility test entrypoint |

## Domain Model

### Entity Summary

| Model | Purpose |
| --- | --- |
| `Product` | Product registered by a Product Owner |
| `ProductDeveloper` | Assignment of one developer to one product |
| `DefectReport` | Main defect/bug report |
| `DefectComment` | Comment attached to a defect |
| `DefectStatusHistory` | Audit record for status transitions |

### ER Diagram

```mermaid
erDiagram
    PRODUCT ||--o{ PRODUCT_DEVELOPER : has
    PRODUCT ||--o{ DEFECT_REPORT : owns
    DEFECT_REPORT ||--o{ DEFECT_COMMENT : has
    DEFECT_REPORT ||--o{ DEFECT_STATUS_HISTORY : has
    DEFECT_REPORT ||--o{ DEFECT_REPORT : duplicate_children

    PRODUCT {
        string product_id PK
        string name
        string owner_id
    }

    PRODUCT_DEVELOPER {
        bigint id PK
        string product_id FK
        string developer_id UK
    }

    DEFECT_REPORT {
        string report_id PK
        string product_id FK
        string version
        string title
        text description
        text steps
        string tester_id
        email tester_email
        string status
        string severity
        string priority
        string backlog_ref
        string assignee_id
        string duplicate_of_id FK
        text fix_note
        text retest_note
        datetime received_at
        datetime decided_at
        datetime updated_at
    }

    DEFECT_COMMENT {
        bigint id PK
        string defect_id FK
        string author_id
        text text
        datetime created_at
    }

    DEFECT_STATUS_HISTORY {
        bigint id PK
        string defect_id FK
        string from_status
        string to_status
        string actor_id
        datetime changed_at
    }

```

Tenant registry entities are stored separately in the `tenancy` app:

```mermaid
erDiagram
    TENANT ||--o{ DOMAIN : maps

    TENANT {
        bigint id PK
        string schema_name UK
        string domain UK
        string name
        boolean is_active
        datetime created_at
    }

    DOMAIN {
        bigint id PK
        string domain UK
        bigint tenant_id FK
        boolean is_primary
    }
```

### Notes On Identity

The system does not define custom `User` models. It uses Django's built-in auth users and groups.

Role membership is group-based:

- `owner`
- `developer`
- `platform_admin`

Domain models store user references as string IDs:

- `Product.owner_id`
- `ProductDeveloper.developer_id`
- `DefectReport.tester_id`
- `DefectReport.assignee_id`
- `DefectComment.author_id`
- `DefectStatusHistory.actor_id`

These are matched against `User.username`.

## Defect Lifecycle

The central status machine is implemented in `defects.services.apply_action`.

```mermaid
stateDiagram-v2
    [*] --> New : create_defect
    New --> Open : accept_open / owner
    New --> Rejected : reject / owner
    New --> Duplicate : duplicate / owner
    Open --> Assigned : take_ownership / developer
    Reopened --> Assigned : take_ownership / developer
    Assigned --> Fixed : set_fixed / assigned developer
    Assigned --> Cannot_Reproduce : cannot_reproduce / assigned developer
    Fixed --> Resolved : set_resolved / owner
    Fixed --> Reopened : reopen / owner
```

Additional action:

- `add_comment` does not change status.
- Every status transition records `DefectStatusHistory`.
- Most status transitions call `_notify_transition`, which sends tester email and duplicate-chain notifications when applicable.

## Backend API

### API Route Table

| Method | Path | View | Auth | Role |
| --- | --- | --- | --- | --- |
| `POST` | `/api/defects/new/` | `DefectCreateApi` | public | external tester/system |
| `GET` | `/api/defects/` | `DefectListApi` | required | owner or developer |
| `GET` | `/api/defects/<defect_id>/` | `DefectDetailApi` | required | owner or developer |
| `POST` | `/api/defects/<defect_id>/actions/` | `DefectActionApi` | required | depends on action |
| `POST` | `/api/products/register/` | `ProductRegisterApi` | required | owner |
| `POST` | `/api/tenants/register/` | `TenantRegisterApi` | required | platform_admin or superuser |
| `GET` | `/api/developers/<developer_id>/effectiveness/` | `DeveloperEffectivenessApi` | required | owner |

### API Controller Pattern

API views follow this pattern:

```text
HTTP request
-> DRF APIView
-> serializer validates request shape
-> actor_from_user extracts role context
-> service function enforces business rules
-> model updates happen in service layer
-> JSON response returned
```

### Product Registration

`ProductRegisterApi` calls `register_product`.

Rules:

- Only Product Owner can register products.
- Owner username becomes `Product.owner_id`.
- Product ID must be unique.
- One owner can register at most one product.
- Developers must exist as Django users, be in group `developer`, and not already be assigned to another product.

### Tenant Registration

`tenancy.views.TenantRegisterApi` calls `tenancy.services.register_tenant`.

Rules:

- Only platform admin or superuser can register tenants.
- `schema_name` must be lowercase letters/digits/underscore and start with a letter.
- Reserved names such as `public` and `information_schema` are rejected.
- Domain must pass domain format validation.
- Schema and domain must be unique.

In tenant mode, creating `tenancy.Tenant` uses `TenantMixin.auto_create_schema=True`, so a new PostgreSQL schema is created and migrated.

### Platform Tenant Console

`tenancy.views.platform_tenant_list` renders the public-schema tenant management UI at:

```text
/platform/tenants/
```

Rules:

- Only public schema can access it.
- Only platform admins or superusers can access it.
- It has its own login/logout routes, so `platform_admin` group users do not need Django admin staff access.
- It lists tenants, domains, and public platform domains from `PUBLIC_SCHEMA_DOMAINS`.
- It can create tenants, create the initial tenant admin account in the tenant schema, and add domains to existing tenants.

### Developer Effectiveness

`DeveloperEffectivenessApi` calls `summarize_developer_effectiveness`.

Rules:

- Only Product Owners can call it.
- Developer must belong to one of the owner's products.
- `fixed` count comes from status history transitions to `Fixed` by that developer.
- `reopened` count comes from status history transitions to `Reopened`.
- Classification is handled by `classify_developer(fixed, reopened)`:
  - `fixed < 20`: `Insufficient data`
  - `reopened / fixed < 1/32`: `Good`
  - `1/32 <= reopened / fixed < 1/8`: `Fair`
  - `reopened / fixed >= 1/8`: `Poor`

## Frontend App

The `frontend` app is a traditional server-rendered Django UI. It does not call the JSON API from JavaScript. Instead, frontend views call the same service functions used by API views.

### File Responsibilities

| File | Responsibility |
| --- | --- |
| `views.py` | Login, board, product registration, defect creation, defect detail/action handling |
| `urls.py` | Frontend routes |
| `templates/frontend/*.html` | HTML pages |
| `static/frontend/styles.css` | Styling |
| `static/frontend/app.js` | Small UI helpers for status filter and clickable defect rows |
| `tests.py` | Frontend smoke tests |

### Frontend Route Table

| Method | Path | View | Purpose |
| --- | --- | --- | --- |
| `GET` | `/` | `home` | Defect board |
| `GET/POST` | `/auth/` | `external_auth` | Login |
| `GET` | `/auth/logout/` | `sign_out` | Logout |
| `GET/POST` | `/products/register/` | `register_product` | Product registration page |
| `GET/POST` | `/defects/new/` | `create_defect` | Testing-only defect creation page |
| `GET/POST` | `/<defect_id>/` | `defect_detail` | Defect detail and lifecycle actions |

### Frontend Request Flow

```mermaid
sequenceDiagram
    participant U as User Browser
    participant FV as frontend.views
    participant Auth as actor_from_user
    participant S as defects.services
    participant M as models
    participant T as template

    U->>FV: GET / or POST form
    FV->>Auth: derive role from request.user groups
    FV->>S: call service for create/action/register
    S->>M: query/update database
    FV->>T: render template with messages/data
    T-->>U: HTML response
```

### API Versus Frontend Interaction

The frontend and API are parallel entrypoints:

```text
Frontend form POST -> frontend.views -> defects.services -> defects.models
API JSON request   -> defects.views    -> defects.services -> defects.models
```

This means business rules should be changed in `defects/services.py`, not duplicated in views.

## Multi-Tenancy Architecture

Tenant mode is optional and is controlled by:

```env
ENABLE_DJANGO_TENANTS=True
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/betatrax
```

When enabled:

```mermaid
flowchart TD
    Request[HTTP request with Host header]
    Middleware[TenantMainMiddleware]
    Domain[tenancy.Domain in public schema]
    Tenant[tenancy.Tenant]
    Schema[PostgreSQL tenant schema]
    View[Django view]

    Request --> Middleware
    Middleware --> Domain
    Domain --> Tenant
    Tenant --> Schema
    Schema --> View
```

Important behavior:

- Tenant is selected by hostname before normal view logic runs.
- Hostnames listed in `PUBLIC_SCHEMA_DOMAINS` route to the public schema URL set.
- If no `Domain.domain` matches the hostname and no public-domain rule applies, `SHOW_PUBLIC_IF_NO_TENANT_FOUND=True` routes to public schema; otherwise the app returns `No tenant for hostname`.
- Shared/public schema stores tenant registry data in `tenancy`.
- Tenant schemas store tenant-scoped product and defect data in `defects`.
- Public schema routes use `betatrax.public_urls`; tenant routes use `betatrax.urls`.
- `PUBLIC_SCHEMA_DOMAINS` is the preferred deployment setting for the platform tenant console.

See `documents/tenant-usage.md` for operational commands and local testing steps.

## Email Architecture

Email is configured in `settings.py`.

Modes:

- `EMAIL_ENABLED=False`: console email backend, useful for local/demo testing.
- `EMAIL_ENABLED=True`: SMTP backend using variables such as `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`.

Email sends happen in `defects.services`:

- `_notify_status_change`
- `_notify_duplicate_chain_on_root_change`
- `_notify_transition`

Emails are triggered after lifecycle status transitions.

## Database Migrations

`defects/migrations`:

- `0001_initial.py`: core product, developer, defect, comment, history models.
- `0002_tenant_model.py`: legacy tenant model from the first Sprint 3 tenant implementation.
- `0003_alter_tenant_schema_name_domain.py`: legacy tenant domain model.
- `0004_delete_domain_delete_tenant.py`: removes legacy tenant registry models from the tenant-scoped app.

`tenancy/migrations`:

- `0001_initial.py`: current public-schema tenant and domain registry. It also copies data from legacy `defects_tenant` and `defects_domain` tables when upgrading an existing database.

`frontend/migrations/0001_initial.py` exists but the `frontend` app has no active domain models.

Migration command choice:

| Mode | Command |
| --- | --- |
| Normal SQLite/PostgreSQL | `python manage.py migrate` |
| Tenant shared schema | `python manage.py migrate_schemas --shared --noinput` |
| New tenant schema | Created automatically when `Tenant` is saved |

Startup migrations do not create a public platform superuser automatically. The first public admin is created manually with `python manage.py createsuperuser`. Tenant admin users are created by the platform tenant console when creating a tenant.

## Deployment Architecture

### Docker

`Dockerfile`:

- Uses `python:3.12-slim`.
- Installs `requirements.txt`.
- Copies project into `/app`.
- Exposes port `8000`.
- Uses `docker-entrypoint.sh`.
- Starts `python manage.py runserver 0.0.0.0:8000`.

`docker-entrypoint.sh`:

- Waits for database connectivity.
- If `AUTO_MIGRATE=True`, runs migrations before starting the server.
- If `ENABLE_DJANGO_TENANTS=True`, runs:

```bash
python manage.py migrate_schemas --shared --noinput
```

- Otherwise runs:

```bash
python manage.py migrate --noinput
```

### Environment Variables

Important variables:

| Variable | Purpose |
| --- | --- |
| `DJANGO_DEBUG` | Enables debug mode |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated trusted origins |
| `DATABASE_URL` | Database URI, for example `sqlite:///./data/db.sqlite3` or `postgresql://user:password@host:5432/dbname` |
| `ENABLE_DJANGO_TENANTS` | Enables django-tenants mode |
| `PUBLIC_SCHEMA_DOMAINS` | Comma-separated public/platform hostnames |
| `SHOW_PUBLIC_IF_NO_TENANT_FOUND` | Uses public URL routes when an allowed host has no tenant domain |
| `AUTO_MIGRATE` | Runs migration on container startup |
| `DATABASE_WAIT_TIMEOUT` | Database wait timeout in seconds |
| `EMAIL_ENABLED` | Enables SMTP email |

## CI/CD Architecture

### CI

`.github/workflows/ci.yml`:

- Installs Python 3.12 dependencies.
- Runs `manage.py check`.
- Verifies migrations with `makemigrations --check --dry-run`.
- Runs service, frontend, APIClient, APIRequestFactory, discovered tests, compatibility tests.
- Runs branch coverage.
- Uploads `coverage.xml` and `htmlcov/`.

### Auto Release

`.github/workflows/auto-release.yml`:

- Runs after successful CI on `main` or manually.
- Reads `VERSION`.
- Creates or updates GitHub Release.
- Skips release for README/AGENTS/workflow-only changes.

### Container Image

`.github/workflows/container-image.yml`:

- Runs after successful CI on `main` or manually.
- Builds and pushes image to GHCR.
- Uses `VERSION` as tag.
- Adds `latest` for automatic runs.
- Skips image build for README/AGENTS/workflow-only changes.

## Test Architecture

```text
defects.testsuite.base
+-- shared APITestCase fixtures
+-- owner/developer users
+-- product/developer assignment
+-- seeded defect

defects.testsuite.test_services
+-- service-layer unit tests
+-- lifecycle transition rules
+-- email/duplicate chain behavior
+-- product registration rules
+-- tenant registration rules
+-- effectiveness summary rules

defects.testsuite.test_api_client
+-- endpoint-level tests through DRF APIClient
+-- submit/list/detail/action flows
+-- role restrictions
+-- product/tenant/effectiveness endpoints

defects.testsuite.test_views_request_factory
+-- direct view tests through APIRequestFactory
+-- focused controller edge cases

defects.testsuite.test_effectiveness
+-- branch-focused classify_developer tests

frontend.tests
+-- server-rendered page smoke tests
+-- login/logout
+-- product registration page
+-- defect creation page
+-- defect detail/actions
```

## Key Data Flows

### Submit Defect Through API

```mermaid
sequenceDiagram
    participant Client
    participant API as DefectCreateApi
    participant Ser as DefectCreateSerializer
    participant S as create_defect
    participant DB as Database

    Client->>API: POST /api/defects/new/
    API->>Ser: validate required fields and email
    API->>DB: find Product by product_id
    API->>S: create_defect(product, payload)
    S->>DB: insert DefectReport(status=New)
    S->>DB: insert DefectStatusHistory(New -> New)
    API-->>Client: 201 report_id/status
```

### Apply Defect Action

```mermaid
sequenceDiagram
    participant User
    participant View as API or frontend view
    participant Auth as actor_from_user
    participant S as apply_action
    participant DB as Database
    participant Mail as Email backend

    User->>View: POST action
    View->>Auth: derive ActorContext
    View->>S: apply_action(defect, action, payload, actor)
    S->>S: validate status + role + ownership
    S->>DB: update DefectReport
    S->>DB: insert DefectStatusHistory
    S->>Mail: send transition notifications
    View-->>User: JSON response or redirect with message
```

### Register Product

```mermaid
sequenceDiagram
    participant Owner
    participant View as ProductRegisterApi or frontend view
    participant S as register_product
    participant Auth as Django User/Group
    participant DB as Database

    Owner->>View: product_id, name, developers
    View->>S: register_product(owner_user, ...)
    S->>DB: ensure owner has no product
    S->>DB: ensure product_id is unique
    S->>Auth: ensure developers exist and are in developer group
    S->>DB: create Product
    S->>DB: create ProductDeveloper rows
    View-->>Owner: created response or redirect
```

## Architectural Strengths

- API and frontend share the same service layer, reducing duplicated business logic.
- Status transition rules are centralized in `apply_action`.
- Role extraction is centralized in `actor_from_user`.
- Tests cover service logic, API integration, direct view behavior, frontend smoke flows, and branch-focused effectiveness logic.
- Docker startup handles migration automatically.
- Tenant usage is optional, which keeps normal local/CI setup simple.

## Current Architectural Risks And Limitations

- `SECRET_KEY` has a hardcoded fallback in `settings.py`; production should read it from environment.
- `DEBUG=True` is convenient locally but should be false in production.
- `runserver` is used in Docker; production deployments normally use a WSGI/ASGI server such as Gunicorn or Uvicorn.
- User references in business models are stored as strings, not foreign keys to Django `User`; this simplifies seed/demo flows but weakens referential integrity.
- Frontend pages call services directly instead of consuming the JSON API; this is acceptable for Django server-rendered apps, but API and UI behavior can still diverge at the controller/template level.
- Duplicate action UI has a button but no frontend input for choosing a duplicate root report; the API/service supports `duplicate_of`.

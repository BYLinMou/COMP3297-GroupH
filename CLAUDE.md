# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

Activate the conda environment first if packages are missing:
```bash
conda activate betatrax
```

Copy `.env.example` to `.env` before running locally. Default config uses SQLite — no extra setup needed.

## Common Commands

**Run the dev server:**
```bash
python manage.py runserver
```

**Check for configuration errors and pending migrations:**
```bash
python manage.py check
python manage.py makemigrations --check --dry-run
```

**Run all non-tenant tests (single-schema, SQLite):**
```bash
python manage.py test betatrax.suite_single_schema --verbosity 2
```

**Run a focused test layer:**
```bash
python manage.py test defects.testsuite.test_services --verbosity 2
python manage.py test defects.testsuite.test_api_client --verbosity 2
python manage.py test defects.testsuite.test_views_request_factory --verbosity 2
python manage.py test defects.testsuite.test_effectiveness --verbosity 2
python manage.py test frontend.tests --verbosity 2
```

**Run a single test method:**
```bash
python manage.py test defects.testsuite.test_services.ServiceLayerTests.test_create_defect --verbosity 2
```

**Run branch coverage and verify the 100% gate (required by course):**
```bash
python -m coverage run --branch --omit=*/migrations/*,tenancy/test_tenant_mode_integration.py,betatrax/suite_tenant_mode.py,manage.py,*/asgi.py,*/wsgi.py manage.py test betatrax.suite_single_schema --verbosity 2
python -m coverage report --fail-under=100
python -m coverage html
```

**Run tenant-mode tests (requires PostgreSQL and `ENABLE_DJANGO_TENANTS=True`):**
```bash
export ENABLE_DJANGO_TENANTS=True
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/betatrax
python -m coverage run --branch --source=tenancy --omit=*/migrations/*,tenancy/tests.py,manage.py,*/asgi.py,*/wsgi.py manage.py test betatrax.suite_tenant_mode --verbosity 2
python -m coverage report --fail-under=100
```

**Apply migrations:**
```bash
# Normal mode (SQLite or plain PostgreSQL)
python manage.py migrate

# Tenant mode (PostgreSQL + django-tenants)
python manage.py migrate_schemas --shared
```

## Architecture

The primary surface is the **JSON API** in `defects/`. The `frontend/` app is secondary and optional — the course focuses on backend API features and their test coverage.

### The Service Layer Boundary

All business logic lives in **`defects/services.py`**. Both API views (`defects/views.py`) and frontend views (`frontend/views.py`) call the same service functions — never duplicate logic between them. The pattern for every API request is:

```
HTTP request → DRF APIView → serializer validates shape → actor_from_user extracts role → service enforces rules → model update → JSON response
```

### Role and Authorization

`defects/authz.py` defines `ActorContext` and `actor_from_user()`. Roles are Django group memberships: `owner`, `developer`, `platform_admin`. Domain models store user references as plain string IDs (e.g. `Product.owner_id`, `DefectReport.assignee_id`) matched against `User.username` — there are no FK relationships to the auth user table.

### Defect Lifecycle

The state machine is entirely in `defects/services.py` → `apply_action()`. Valid transitions:

```
New → Open (owner: accept_open)
New → Rejected (owner: reject)
New → Duplicate (owner: duplicate)
Open → Assigned (developer: take_ownership)
Reopened → Assigned (developer: take_ownership)
Assigned → Fixed (assigned developer: set_fixed)
Assigned → Cannot Reproduce (assigned developer: cannot_reproduce)
Fixed → Resolved (owner: set_resolved)
Fixed → Reopened (owner: reopen)
```

`add_comment` is a no-status-change action available to both roles.

### Multi-Tenancy (Optional)

Enabled via `ENABLE_DJANGO_TENANTS=True` in `.env`, requires PostgreSQL. When active:
- Requests are routed to tenant schemas by hostname before view logic runs.
- Hostnames in `PUBLIC_SCHEMA_DOMAINS` use the public schema (`betatrax/public_urls.py`) and expose only the platform tenant console.
- All other hostnames resolve a `tenancy.Domain` row → `tenancy.Tenant` → PostgreSQL schema.
- The `tenancy/` app lives in the public schema; `defects/` app lives inside each tenant schema.

When `ENABLE_DJANGO_TENANTS=False` (default), the app runs as a single-schema Django app against SQLite or PostgreSQL and `tenancy/` is effectively unused.

### Test Architecture

Tests are split into two non-overlapping suites to avoid mode conflicts:

- **`betatrax/suite_single_schema`** — runs in SQLite mode; covers `defects/` and `frontend/`
- **`betatrax/suite_tenant_mode`** — runs with PostgreSQL + `django-tenants`; covers `tenancy/`

The shared test base class is `defects/testsuite/base.py` → `DefectApiTestCase`. It pre-creates owner/developer users, a product, and a seed defect in `setUp()`. Use its helper methods (`move_defect_to_open`, `move_defect_to_assigned`, `move_defect_to_fixed`) to advance state without repeating transition code.

Coverage is measured with `--branch` and must reach 100% for both suites. Coverage config is in `.coveragerc`; it sources `defects`, `frontend`, and `tenancy`, omitting migrations, entrypoints, and the cross-suite test files.

### Versioning and Commits

Update the `VERSION` file after completing a core feature (increment minor) or during incremental work (increment alpha suffix, e.g. `0.3.0-alpha.1 → 0.3.0-alpha.2`). Commit after each core function is complete.

After any API or feature change, update the relevant files under `documents/` and `README.md`.

---

COMP3297 Software Engineering
School of Computing and Data Science
Department of Computer Science
BetaTrax Final Review Setup
Overview
The Final Project Review is similar to the Sprint 1 Review, but with further scenarios and additional
demos covering, for example, your automated testing.
Reminder from the Sprint 3 Task Sheet and Sprint 3 Deliverables: You must bring to the Review:
o your BetaTrax source code ready to run through a number of scenarios to demonstrate required
functionality, and to demonstrate its support for multi-tenancy, authentication and role-based
access.
o your automated tests for the successful execution of each method available on each endpoint. A
single test for each endpoint method is sufficient.
o your automated white-box tests for branch coverage of the code that classifies developer
effectiveness. You will execute these with a coverage tool to demonstrate the adequacy of this
small test set.
o your API documentation. We will refer to it during the Review.
As before, if your implementation requires details that are not specified, you can provide your own. For
instance, if your implementation of Tenant, Product Owner or Developer models requires you to initialize
fields that are not specified here, you may provide your own values.
Setup for Demo
Tenants
Two tenants in addition to your public tenant:
The part of the demo that executes most of the scenarios will use only the first tenant, SE Tenant 1.
A subsequent part of the demo will use the second tenant.
Setup for SE Tenant 1
Users
Five users:
Products
One product:
with user_1 as Product Owner and user_2 as Developer
name (if you have such a field) SE Tenant 1 SE Tenant 2
schema_name se1 se2
domain se1.localhost se2.localhost
username user_1 user_2 user_3 user_4 user_5
Product ID prod_1Defect Reports for prod_1
One report:
* assigned and linked to the single developer, user_2.
Setup for SE Tenant 2
Users
Three users:
Products
One product:
with user_6 as Product Owner, and user_7 and user_8 as Developers.
Defect Reports for prod_1
One report:
*assigned and linked to developer, user_7.
Product ID prod_1
Version 0.9.0
Title Unable to search
Description Search button unresponsive after
completing an initial search
Steps to
Reproduce
1. Complete a search
2. Modify search criteria
3. Click Search button
Tester ID Tester_1
Email icyreward@gmail.com
Received 2026-03-25 10:53
Status Assigned *
Severity Major
Priority High
username user_6 user_7 user_8
Product ID prod_1 (same ID as for previous tenant, different product)
Product ID Prod_1
Version 0.9.0
Title Hit count incorrect
Description Following a successful search, the hit count is different to the
number of matches displayed.
Steps to
Reproduce
1. Enter search criteria that ensure at least one match
2. Search
3. Compare matches displayed with the number of hits reported.
Tester ID Tester_1
Email icyreward@gmail.com
Received 2026-04-27 15:37
Status Assigned*
Severity Minor
Priority HighComments
Comment added to the defect report by user_7 (the developer):
Comment added to the defect report by user_6 (the product owner):
Developer Metrics for user_7
Set up for user_7 such that the current values for:
o defects reported as fixed = 8
o defects reopened = 1
The way you set up these values will be dependent on your implementation.
text Comment added by developer
date 2026-04-26 20:49
text Comment added by product owner
date 2026-04-26 23:27
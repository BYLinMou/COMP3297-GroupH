# Tenant Usage Guide

This document explains how BetaTrax tenant mode works and how to test it locally.

Tenant mode is enabled by:

```env
ENABLE_DJANGO_TENANTS=True
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/betatrax
```

Do not use tenant mode with SQLite. `django-tenants` requires PostgreSQL schemas.

## Mental Model

BetaTrax uses `django-tenants`.

There are two layers:

- Public/shared schema: stores tenant registry data, including `Tenant` and `Domain`.
- Tenant schema: stores the application data for one tenant.
- Code location: tenant registry models live in `tenancy`; product and defect models live in `defects`.

The browser does not choose a tenant by login first. It chooses a tenant by hostname.

Examples:

- `http://127.0.0.1:8000/` looks for a `Domain` row with `domain="127.0.0.1"`.
- `http://team-a.localhost:8000/` looks for a `Domain` row with `domain="team-a.localhost"`.
- `https://team-a.example.com/` looks for a `Domain` row with `domain="team-a.example.com"`.

If no matching `Domain` exists and `SHOW_PUBLIC_IF_NO_TENANT_FOUND=False`, Django shows:

```text
No tenant for hostname "..."
```

That means the server is running, but the hostname is not mapped to a tenant.

If the hostname is listed in `PUBLIC_SCHEMA_DOMAINS`, it uses the public schema URL set. That public URL set exposes the platform tenant console, platform admin, and tenant registration, not tenant business pages.

## Local .env

Use PostgreSQL and tenant mode:

```env
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/betatrax
ENABLE_DJANGO_TENANTS=True

AUTO_MIGRATE=True
DATABASE_WAIT_TIMEOUT=60
PUBLIC_SCHEMA_DOMAINS=platform.localhost
SHOW_PUBLIC_IF_NO_TENANT_FOUND=True
```

If you only want normal single-database mode, set:

```env
ENABLE_DJANGO_TENANTS=False
```

`PUBLIC_SCHEMA_DOMAINS` is the public/platform entrypoint. Do not create a `Domain` row for that hostname.

## Initialize An Empty Database

For tenant mode, do not use normal `migrate` as the main command.

Run:

```powershell
C:\Users\User\.conda\envs\betatrax\python.exe manage.py migrate_schemas --shared --noinput
```

This creates the public/shared tables, including `tenancy_tenant` and `tenancy_domain`.
Demo defect seed data is skipped during this public-schema migration because
`defects_*` tables are tenant-scoped and are created inside tenant schemas.

If you are using Docker with the project entrypoint and `AUTO_MIGRATE=True`, the container runs this automatically when `ENABLE_DJANGO_TENANTS=True`.

## Create The First Local Tenant

After shared migrations, create a tenant for local browser access:

```powershell
C:\Users\User\.conda\envs\betatrax\python.exe manage.py shell -c "from tenancy.models import Tenant, Domain; t, _ = Tenant.objects.get_or_create(schema_name='local', defaults={'domain':'127.0.0.1','name':'Local Company'}); Domain.objects.get_or_create(domain='127.0.0.1', defaults={'tenant':t,'is_primary':True}); print('ok')"
```

This creates:

- A tenant/company named `local`
- A domain mapping `127.0.0.1 -> local`
- A PostgreSQL schema named `local`
- The tenant schema tables, because `Tenant.auto_create_schema=True`

Then start the server:

```powershell
C:\Users\User\.conda\envs\betatrax\python.exe manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

## Create Multiple Tenants Locally

Create tenant A:

```powershell
C:\Users\User\.conda\envs\betatrax\python.exe manage.py shell -c "from tenancy.models import Tenant, Domain; t, _ = Tenant.objects.get_or_create(schema_name='team_a', defaults={'domain':'team-a.localhost','name':'Team A'}); Domain.objects.get_or_create(domain='team-a.localhost', defaults={'tenant':t,'is_primary':True}); print('ok')"
```

Create tenant B:

```powershell
C:\Users\User\.conda\envs\betatrax\python.exe manage.py shell -c "from tenancy.models import Tenant, Domain; t, _ = Tenant.objects.get_or_create(schema_name='team_b', defaults={'domain':'team-b.localhost','name':'Team B'}); Domain.objects.get_or_create(domain='team-b.localhost', defaults={'tenant':t,'is_primary':True}); print('ok')"
```

On Windows, edit the hosts file as Administrator:

```text
C:\Windows\System32\drivers\etc\hosts
```

Add:

```text
127.0.0.1 team-a.localhost
127.0.0.1 team-b.localhost
```

Then use:

```text
http://team-a.localhost:8000/
http://team-b.localhost:8000/
```

These two hostnames enter different tenant schemas.

## How To Switch Tenants

You switch tenants by changing the hostname in the browser.

Use tenant A:

```text
http://team-a.localhost:8000/
```

Use tenant B:

```text
http://team-b.localhost:8000/
```

Use the local default tenant:

```text
http://127.0.0.1:8000/
```

This is why tenant mode can feel confusing: login is not the first selector. The hostname selects the tenant first, then normal login/auth happens inside that tenant context.

## Admin Pages

The admin model list depends on the current schema:

- Public schema: shows platform/shared models such as `Tenant` and `Domain`.
- Tenant schema such as `local`, `team_a`, or `team_b`: shows tenant business models such as `Product`, `DefectReport`, comments, and status history.

If you open `/admin/` through `http://127.0.0.1:8000/` and `127.0.0.1` is mapped to the `local` tenant, you are inside the `local` company schema. In that context, `Tenant` and `Domain` should not appear.

## Platform Tenant Console

Open the public tenant console through a hostname from `PUBLIC_SCHEMA_DOMAINS`:

```text
http://platform.localhost:8000/platform/tenants/
```

Unauthenticated users are redirected to:

```text
http://platform.localhost:8000/platform/login/
```

This page is for platform admins only. Platform users can be superusers or members of the `platform_admin` group. It can:

- Show all tenants/companies.
- Create a tenant/company with schema name, first domain, company name, and tenant admin account.
- Add extra domains to an existing tenant/company.

For local testing, add this to the Windows hosts file if needed:

```text
127.0.0.1 platform.localhost
```

Then make sure `platform.localhost` is in `.env`:

```env
PUBLIC_SCHEMA_DOMAINS=platform.localhost
```

Do not add `platform.localhost` to `tenancy.Domain`. Tenant domains are for company entrypoints such as `team-a.localhost`; public domains are for platform administration.

## Public And Tenant Admin Accounts

Startup migrations do not create a public superuser automatically. For a new database, create the first public/platform admin manually:

```powershell
C:\Users\User\.conda\envs\betatrax\python.exe manage.py createsuperuser
```

Use that account to sign in at:

```text
http://platform.localhost:8000/platform/login/
```

When you create a tenant in `/platform/tenants/`, the form also asks for a tenant admin username, email, and password. That account is created inside the tenant schema, not public schema.

Example:

- Public admin logs into `platform.localhost`.
- Public admin creates tenant `team_a` with domain `team-a.localhost`.
- Public admin enters tenant admin username `team-a-admin`.
- `team-a-admin` can log into `http://team-a.localhost:8000/admin/`.
- The public admin account is separate and does not automatically log into `team-a.localhost`.

## Check Current Tenants

Run:

```powershell
C:\Users\User\.conda\envs\betatrax\python.exe manage.py shell -c "from tenancy.models import Tenant, Domain; print('tenants', list(Tenant.objects.values_list('schema_name','domain'))); print('domains', list(Domain.objects.values_list('domain','tenant__schema_name','is_primary')))"
```

Expected example:

```text
tenants [('local', '127.0.0.1'), ('team_a', 'team-a.localhost')]
domains [('127.0.0.1', 'local', True), ('team-a.localhost', 'team_a', True)]
```

## Test With curl

You can test a tenant without editing the hosts file by setting the `Host` header:

```powershell
curl.exe -H "Host: team-a.localhost" http://127.0.0.1:8000/
```

For API calls:

```powershell
curl.exe -H "Host: team-a.localhost" http://127.0.0.1:8000/api/products/register/
```

The request will be routed to the tenant whose `Domain.domain` is `team-a.localhost`.

## Register Tenant API

The API endpoint is:

```text
POST /api/tenants/register/
```

It requires a Platform Admin user.

Request body:

```json
{
  "schema_name": "team_a",
  "domain": "team-a.localhost",
  "name": "Team A"
}
```

In tenant mode, successful registration creates:

- `Tenant(schema_name="team_a")`
- `Domain(domain="team-a.localhost")`
- PostgreSQL schema `team_a`
- Tenant schema migrations

For a completely empty database, you still need shared migrations first:

```powershell
C:\Users\User\.conda\envs\betatrax\python.exe manage.py migrate_schemas --shared --noinput
```

## Common Errors

### No tenant for hostname "127.0.0.1"

The server is running, but no `Domain` row matches `127.0.0.1`.

Fix:

```powershell
C:\Users\User\.conda\envs\betatrax\python.exe manage.py shell -c "from tenancy.models import Tenant, Domain; t, _ = Tenant.objects.get_or_create(schema_name='local', defaults={'domain':'127.0.0.1','name':'Local Company'}); Domain.objects.get_or_create(domain='127.0.0.1', defaults={'tenant':t,'is_primary':True}); print('ok')"
```

### ENABLE_DJANGO_TENANTS=True requires a PostgreSQL DATABASE_URL

Tenant mode is enabled, but the app is not configured to use PostgreSQL.

Fix `.env`:

```env
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/betatrax
ENABLE_DJANGO_TENANTS=True
```

### TENANT_APPS setting not set

The running image/code is older than the tenant settings fix.

Fix:

- Pull/build a newer image.
- Confirm the code contains `SHARED_APPS` and `TENANT_APPS` in `betatrax/settings.py`.

### I created a tenant but still get no tenant

Check that the browser hostname exactly matches the `Domain.domain` value.

For example, this domain:

```text
team-a.localhost
```

matches:

```text
http://team-a.localhost:8000/
```

It does not match:

```text
http://127.0.0.1:8000/
```

unless you also create a `Domain` row for `127.0.0.1`.

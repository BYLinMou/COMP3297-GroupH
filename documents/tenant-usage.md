# Tenant Usage Guide

This document explains how BetaTrax tenant mode works and how to test it locally.

Tenant mode is enabled by:

```env
ENABLE_DJANGO_TENANTS=True
DATABASE_ENGINE=postgresql
```

Do not use tenant mode with SQLite. `django-tenants` requires PostgreSQL schemas.

## Mental Model

BetaTrax uses `django-tenants`.

There are two layers:

- Public/shared schema: stores tenant registry data, including `Tenant` and `Domain`.
- Tenant schema: stores the application data for one tenant.

The browser does not choose a tenant by login first. It chooses a tenant by hostname.

Examples:

- `http://127.0.0.1:8000/` looks for a `Domain` row with `domain="127.0.0.1"`.
- `http://team-a.localhost:8000/` looks for a `Domain` row with `domain="team-a.localhost"`.
- `https://team-a.example.com/` looks for a `Domain` row with `domain="team-a.example.com"`.

If no matching `Domain` exists, Django shows:

```text
No tenant for hostname "..."
```

That means the server is running, but the hostname is not mapped to a tenant.

## Local .env

Use PostgreSQL and tenant mode:

```env
DATABASE_ENGINE=postgresql
ENABLE_DJANGO_TENANTS=True

POSTGRES_DB=betatrax
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432

AUTO_MIGRATE=True
DATABASE_WAIT_TIMEOUT=60
```

If you only want normal single-database mode, set:

```env
ENABLE_DJANGO_TENANTS=False
```

## Initialize An Empty Database

For tenant mode, do not use normal `migrate` as the main command.

Run:

```powershell
C:\Users\User\.conda\envs\betatrax\python.exe manage.py migrate_schemas --shared --noinput
```

This creates the public/shared tables, including the tables used to store tenants and domains.

If you are using Docker with the project entrypoint and `AUTO_MIGRATE=True`, the container runs this automatically when `ENABLE_DJANGO_TENANTS=True`.

## Create The First Local Tenant

After shared migrations, create a tenant for local browser access:

```powershell
C:\Users\User\.conda\envs\betatrax\python.exe manage.py shell -c "from defects.models import Tenant, Domain; t, _ = Tenant.objects.get_or_create(schema_name='local', defaults={'domain':'127.0.0.1','name':'Local Tenant'}); Domain.objects.get_or_create(domain='127.0.0.1', defaults={'tenant':t,'is_primary':True}); print('ok')"
```

This creates:

- A tenant named `local`
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
C:\Users\User\.conda\envs\betatrax\python.exe manage.py shell -c "from defects.models import Tenant, Domain; t, _ = Tenant.objects.get_or_create(schema_name='team_a', defaults={'domain':'team-a.localhost','name':'Team A'}); Domain.objects.get_or_create(domain='team-a.localhost', defaults={'tenant':t,'is_primary':True}); print('ok')"
```

Create tenant B:

```powershell
C:\Users\User\.conda\envs\betatrax\python.exe manage.py shell -c "from defects.models import Tenant, Domain; t, _ = Tenant.objects.get_or_create(schema_name='team_b', defaults={'domain':'team-b.localhost','name':'Team B'}); Domain.objects.get_or_create(domain='team-b.localhost', defaults={'tenant':t,'is_primary':True}); print('ok')"
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

## Check Current Tenants

Run:

```powershell
C:\Users\User\.conda\envs\betatrax\python.exe manage.py shell -c "from defects.models import Tenant, Domain; print('tenants', list(Tenant.objects.values_list('schema_name','domain'))); print('domains', list(Domain.objects.values_list('domain','tenant__schema_name','is_primary')))"
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
C:\Users\User\.conda\envs\betatrax\python.exe manage.py shell -c "from defects.models import Tenant, Domain; t, _ = Tenant.objects.get_or_create(schema_name='local', defaults={'domain':'127.0.0.1','name':'Local Tenant'}); Domain.objects.get_or_create(domain='127.0.0.1', defaults={'tenant':t,'is_primary':True}); print('ok')"
```

### ENABLE_DJANGO_TENANTS=True requires DATABASE_ENGINE=postgresql

Tenant mode is enabled, but the app is not configured to use PostgreSQL.

Fix `.env`:

```env
DATABASE_ENGINE=postgresql
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


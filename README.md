# BetaTrax

BetaTrax is a lightweight defect tracking system built for the COMP3297 software engineering project.
It supports the core bug lifecycle from **New -> Open -> Assigned -> Fixed -> Resolved**.
The current implementation is built on a Django-based architecture (see the `betatrax/` project module).

## Workflows

This repository currently uses three GitHub Actions workflows:

1. **CI check** (`.github/workflows/ci.yml`)
Runs on every push and pull request to validate functionality with:
- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py test`

2. **Auto Release** (`.github/workflows/auto-release.yml`)
Creates a GitHub Release after CI succeeds on `main`.
It can also be triggered manually for alpha/beta releases.
Release version is read from the `VERSION` file by default, or overridden via manual input.

3. **Container Image** (`.github/workflows/container-image.yml`)
Builds and pushes a Docker image to GitHub Container Registry (GHCR) only after CI succeeds on `main`.
It can also be triggered manually with an optional `image_tag` input (for example, `alpha`).
By default, image version tag is read from the `VERSION` file. Automatic runs also update `latest`.
The published image path is `ghcr.io/<owner>/<repo>`.

## Local Development

```bash
# Create and activate conda environment
conda create -n betatrax python=3.12
conda activate betatrax

# Install dependencies
pip install -r requirements.txt

# Copy environment config (edit as needed)
cp .env.example .env

# Apply database migrations
python manage.py migrate

# Start the development server
python manage.py runserver
```

The app will be available at `http://127.0.0.1:8000/`.

## API (Sprint 1)

Base path: `/api/defects/`

### 1) List defects

- Method: `GET`
- Path: `/api/defects/`
- Query params (all optional):
  - `status` (for example `New`, `Open`, `Assigned`, `Fixed`, `Resolved`)
  - `product_id`
  - `owner_id`
  - `developer_id`

Response `200`:

```json
{
  "items": [
    {
      "report_id": "BT-RP-2462",
      "title": "Login timeout in beta region",
      "product_id": "PRD-1007",
      "version": "v1.4.2-beta",
      "tester_id": "tester-014",
      "status": "Open",
      "severity": "High",
      "priority": "P1",
      "assignee_id": "",
      "received_at": "2026-03-25T01:23:45.000000+08:00"
    }
  ]
}
```

### 2) Create defect report

- Method: `POST`
- Path: `/api/defects/new/`
- Content-Type: `application/json`
- Required fields:
  - `product_id`, `version`, `title`, `description`, `steps`, `tester_id`
- Optional fields:
  - `email`

Request example:

```json
{
  "product_id": "PRD-1007",
  "version": "v1.5.0-beta",
  "title": "App crash when saving profile",
  "description": "App exits after pressing Save.",
  "steps": "1) Open profile 2) Edit name 3) Save",
  "tester_id": "tester-009",
  "email": "tester@example.com"
}
```

Responses:
- `201` created (returns `report_id`, `status`)
- `400` missing/invalid fields
- `404` unknown `product_id`

### 3) Defect actions (status transitions / comment)

- Method: `POST`
- Path: `/api/defects/<defect_id>/actions/`
- Content-Type: `application/json`
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
- `accept_open`: `owner_id`, `severity` (`High|Medium|Low`), `priority` (`P1|P2|P3`), `backlog_ref` (optional)
- `reject`: `owner_id`
- `duplicate`: `owner_id`, `duplicate_of` (optional)
- `take_ownership`: `developer_id`
- `set_fixed`: `developer_id`, `fix_note` (optional)
- `cannot_reproduce`: `developer_id`, `fix_note` (optional)
- `set_resolved`: `owner_id`, `retest_note` (optional)
- `reopen`: `owner_id`, `retest_note` (optional)
- `add_comment`: `author`, `comment`

Response `200`:

```json
{
  "message": "Defect moved to Fixed.",
  "report_id": "BT-RP-2462",
  "status": "Fixed"
}
```

Error responses:
- `400` invalid transition, invalid role/user, or validation error
- `404` defect not found

### Optional Email (Google SMTP) （Implementing）

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

## License

This project is licensed under **GNU General Public License v3.0 (GPL-3.0)**.
See the [LICENSE](LICENSE) file for details.

## Contribution Rule

1. Create a feature branch for each task.
2. Keep pull requests small and focused.
3. Add or update tests for behavior changes.
4. Get at least one teammate review before merging.

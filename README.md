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
By default, image version tag is read from the `VERSION` file.
The published image path is `ghcr.io/<owner>/<repo>`.

## Runtime Configuration

BetaTrax reads environment variables from container/runtime environment and also supports a local `.env` file.
Use `.env.example` as the template.

For Docker, the common way is:
- `docker run --env-file .env -p 8000:8000 <your-image>`

## License

This project is licensed under **GNU General Public License v3.0 (GPL-3.0)**.
See the [LICENSE](LICENSE) file for details.

## Contribution Rule

1. Create a feature branch for each task.
2. Keep pull requests small and focused.
3. Add or update tests for behavior changes.
4. Get at least one teammate review before merging.

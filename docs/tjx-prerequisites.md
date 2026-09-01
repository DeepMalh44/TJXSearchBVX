# Build, Run, And Customer Inputs

## Local Prerequisites

- Python 3.11 through 3.13 and Node.js/npm.
- Azure CLI and Azure Developer CLI authenticated to the approved tenant and subscription.
- Permission to deploy Bicep resources and create the required role assignments.
- Microsoft Graph permission for the Entra app configuration step.

## Install And Validate

Use `.venv/Scripts/python.exe -m pip install -e ".[dev]"`, then run `npm ci`,
`npm run typecheck`, `npm run lint`, and `npm run build` from `app/frontend`.

Run `.venv/Scripts/python.exe -m pytest -q` and
`.venv/Scripts/python.exe -m ruff check .` from the repository root.

## Entra And Deployment

Run `scripts/configure_entra_app.py check --tenant-id <tenant>` before the explicit `apply`.
Pass the deployed URL with `--app-url`; no client secret is created. Stage the external files
with `scripts/upload_source_images.py --dry-run` before its explicit Entra-authenticated upload.
The files remain outside this repository. Bicep can provision with a Microsoft placeholder
image; later azd service deployment updates the web app image. Start the manual job only after
the shared image and Entra configuration are deployed.

The SPA reads tenant, public client ID, and delegated scope from FastAPI at runtime, allowing
the same image to move between environments. No keys, connection strings, SAS values, or
client secrets are used.

Conditional Access may reject an old Graph token with `TokenCreatedWithOutdatedPolicies`.
Reauthenticate rather than changing the app or RBAC design.

## Future Customer Validation Inputs

TJX should provide representative images or approved secure URLs, production-like records and
image-linked product IDs, vendor fields and real abbreviation examples, and at least 25 buyer
queries with expected products and current baseline results. The evaluation also needs a
definition of successful top-five results, expected product/update/query volumes, latency,
filter, facet, and sort requirements, and data-residency, privacy, compliance, retention,
security-trimming, and network requirements.

TJX validators should review generated descriptions and attributes, label relevant results,
identify unacceptable false positives, and decide whether measured quality warrants further
investment. A Cosmos schema redesign is not a prerequisite for this evaluation.

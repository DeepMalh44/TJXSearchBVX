"""Finalize Entra redirect configuration and synchronize the ingestion Job image."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request


def required(name: str) -> str:
    """Read a mandatory azd output from the postdeploy environment."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required deployment output: {name}")
    return value


def az(*args: str) -> str:
    """Run Azure CLI non-interactively and return its tab-separated scalar output."""
    executable = shutil.which("az")
    if not executable:
        raise RuntimeError("Azure CLI is required")
    completed = subprocess.run(
        [executable, *args, "--only-show-errors", "--output", "tsv"],
        check=True,
        capture_output=True,
        text=True,
        shell=executable.casefold().endswith((".cmd", ".bat")),
    )
    return completed.stdout.strip()


def wait_for_skill_route(app_uri: str, max_attempts: int = 30) -> None:
    """Wait for the skill route; HTTP 401 proves it is live and authentication is enforced."""
    request = urllib.request.Request(
        f"{app_uri}/api/skills/product-enrichment",
        method="POST",
        data=b'{"values":[]}',
        headers={"Content-Type": "application/json"},
    )
    for attempt in range(1, max_attempts + 1):
        try:
            urllib.request.urlopen(request, timeout=10)
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                print("PASS: product enrichment route is active")
                return
        except urllib.error.URLError:
            pass
        if attempt < max_attempts:
            time.sleep(2)
    raise RuntimeError("Product enrichment route did not become active")


def configure_entra(tenant_id: str, app_uri: str) -> None:
    """Apply redirect/API registration updates while tolerating the known CAE refresh issue."""
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/configure_entra_app.py",
            "apply",
            "--tenant-id",
            tenant_id,
            "--app-url",
            app_uri,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        if completed.stdout.strip():
            print(completed.stdout.strip())
        return
    detail = completed.stderr.strip() or completed.stdout.strip()
    if "TokenCreatedWithOutdatedPolicies" in detail:
        print(
            "WARNING: Entra refresh skipped because Conditional Access requires "
            "reauthentication; existing registration remains active.",
            file=sys.stderr,
        )
        return
    raise RuntimeError(f"Entra configuration failed: {detail}")


def main() -> int:
    """Synchronize job image, apply Search objects, verify routing, and configure Entra."""
    resource_group = required("AZURE_RESOURCE_GROUP")
    app_name = required("AZURE_CONTAINER_APP_NAME")
    job_name = required("AZURE_CONTAINER_JOB_NAME")
    app_uri = required("SERVICE_WEB_URI").rstrip("/")
    tenant_id = required("AZURE_TENANT_ID")

    image = az(
        "containerapp",
        "show",
        "--name",
        app_name,
        "--resource-group",
        resource_group,
        "--query",
        "properties.template.containers[0].image",
    )
    az(
        "containerapp",
        "job",
        "update",
        "--name",
        job_name,
        "--resource-group",
        resource_group,
        "--image",
        image,
    )
    subprocess.run(
        [sys.executable, "scripts/manage_search_objects.py", "apply"],
        check=True,
    )
    wait_for_skill_route(app_uri)
    configure_entra(tenant_id, app_uri)
    print(json.dumps({"appUri": app_uri, "jobImage": image}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
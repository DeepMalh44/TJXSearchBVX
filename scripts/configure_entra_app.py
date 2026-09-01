"""Plan or idempotently configure the single-tenant SPA/API registration through Graph."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPE_VALUE = "Search.Access"


def az_json(*args: str) -> Any:
    az = shutil.which("az")
    if not az:
        raise RuntimeError("Azure CLI is required")
    completed = subprocess.run(
        [az, *args, "--only-show-errors", "-o", "json"],
        check=True,
        capture_output=True,
        text=True,
        shell=az.casefold().endswith((".cmd", ".bat")),
    )
    return json.loads(completed.stdout)


def graph(method: str, path: str, token: str, body: dict[str, Any] | None = None) -> Any:
    request = urllib.request.Request(
        f"{GRAPH}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read()
            return json.loads(content) if content else None
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Graph HTTP {exc.code}: {exc.read().decode()}") from exc


def desired(
    display_name: str, tenant_id: str, app_id: str | None, redirects: list[str]
) -> dict[str, Any]:
    scope_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"api://{tenant_id}/{display_name}/{SCOPE_VALUE}")
    )
    api: dict[str, Any] = {
        "requestedAccessTokenVersion": 2,
        "oauth2PermissionScopes": [
            {
                "id": scope_id,
                "value": SCOPE_VALUE,
                "type": "User",
                "isEnabled": True,
                "adminConsentDisplayName": "Access TJX retail search",
                "adminConsentDescription": (
                    "Access the TJX retail search API as the signed-in user."
                ),
                "userConsentDisplayName": "Access TJX retail search",
                "userConsentDescription": "Access the TJX retail search API as you.",
            }
        ],
    }
    if app_id:
        api["preAuthorizedApplications"] = [{"appId": app_id, "delegatedPermissionIds": [scope_id]}]
    return {
        "displayName": display_name,
        "signInAudience": "AzureADMyOrg",
        "identifierUris": [f"api://{app_id}"] if app_id else [],
        "spa": {"redirectUris": sorted(set(redirects))},
        "api": api,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "apply"), default="check", nargs="?")
    parser.add_argument("--display-name", default="tjx-retail-search-poc")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--app-url", action="append", default=[])
    args = parser.parse_args()
    redirects = ["http://localhost:5173", *(url.rstrip("/") for url in args.app_url)]
    token = az_json("account", "get-access-token", "--resource-type", "ms-graph")["accessToken"]
    escaped = args.display_name.replace("'", "''")
    query = urllib.parse.urlencode({"$filter": f"displayName eq '{escaped}'"})
    matches = graph("GET", f"/applications?{query}", token)["value"]
    if len(matches) > 1:
        raise SystemExit("Multiple matching registrations found; refusing ambiguous mutation")
    current = matches[0] if matches else None
    target = desired(
        args.display_name, args.tenant_id, current.get("appId") if current else None, redirects
    )
    if args.command == "check":
        print(
            json.dumps({"action": "update" if current else "create", "desired": target}, indent=2)
        )
        return 0
    if current:
        graph("PATCH", f"/applications/{current['id']}", token, target)
        app_id = current["appId"]
    else:
        created = graph("POST", "/applications", token, target)
        app_id = created["appId"]
        graph(
            "PATCH",
            f"/applications/{created['id']}",
            token,
            desired(args.display_name, args.tenant_id, app_id, redirects),
        )
    print(json.dumps({"clientId": app_id, "scope": f"api://{app_id}/{SCOPE_VALUE}"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

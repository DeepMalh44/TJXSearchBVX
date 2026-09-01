"""Plan, validate, or explicitly apply POC-owned Azure AI Search objects."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "config" / "search-objects.json"
ENVIRONMENT_REFERENCE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")
PRIVATE_LINK_NAME = "cosmos-products"


class SearchConfigurationError(RuntimeError):
    """Raised when Search object configuration cannot be completed safely."""


def run_az(*arguments: str) -> Any:
    """Run Azure CLI with JSON output and convert failures into configuration errors."""
    az = shutil.which("az")
    if az is None:
        raise SearchConfigurationError("Azure CLI is not installed or is not available on PATH.")
    command = [az, *arguments, "--only-show-errors", "--output", "json"]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        shell=Path(az).suffix.casefold() in {".cmd", ".bat"},
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SearchConfigurationError(f"Azure CLI command failed: {detail}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SearchConfigurationError("Azure CLI returned invalid JSON.") from exc


def expand_environment(value: Any) -> Any:
    """Recursively replace ${NAME} placeholders while preserving JSON scalar types."""
    if isinstance(value, dict):
        return {key: expand_environment(item) for key, item in value.items()}
    if isinstance(value, list):
        return [expand_environment(item) for item in value]
    if not isinstance(value, str):
        return value

    def environment_value(name: str) -> str:
        if name not in os.environ:
            raise SearchConfigurationError(f"Required environment variable is not set: {name}")
        return os.environ[name]

    exact_match = ENVIRONMENT_REFERENCE.fullmatch(value)
    if exact_match:
        raw_value = environment_value(exact_match.group(1))
        try:
            return json.loads(raw_value)
        except json.JSONDecodeError:
            return raw_value

    def replacement(match: re.Match[str]) -> str:
        name = match.group(1)
        return environment_value(name)

    return ENVIRONMENT_REFERENCE.sub(replacement, value)


def request(endpoint: str, api_version: str, item: dict[str, Any], method: str) -> int:
    """Call one Search data-plane object endpoint with the current Azure CLI identity."""
    token = run_az(
        "account", "get-access-token", "--resource", "https://search.azure.com"
    )["accessToken"]
    name = urllib.parse.quote(item["name"], safe="")
    url = f"{endpoint}/{item['kind']}/{name}?api-version={api_version}"
    body = json.dumps(item["payload"]).encode("utf-8") if method == "PUT" else None
    search_request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(search_request, timeout=30) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        if method == "GET" and exc.code == 404:
            return exc.code
        detail = exc.read().decode("utf-8", errors="replace")
        message = f"Search returned HTTP {exc.code} for {item['name']}: {detail}"
        raise SearchConfigurationError(message) from exc


def search_private_link_connections(connections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select only Cosmos private endpoint connections owned by this Search graph."""
    return [
        connection
        for connection in connections
        if connection["properties"]["privateEndpoint"]["id"].rstrip("/").rsplit("/", 1)[-1]
        == PRIVATE_LINK_NAME
    ]


def wait_for_cosmos_private_link(max_attempts: int = 40, delay_seconds: int = 15) -> None:
    """Approve and wait for the Search-managed Cosmos shared private link."""
    cosmos_resource_id = os.environ["AZURE_COSMOS_RESOURCE_ID"]
    search_resource_id = (
        f"/subscriptions/{os.environ['AZURE_SUBSCRIPTION_ID']}"
        f"/resourceGroups/{os.environ['AZURE_RESOURCE_GROUP']}"
        f"/providers/Microsoft.Search/searchServices/{os.environ['AZURE_SEARCH_SERVICE_NAME']}"
    )
    shared_link_url = (
        f"https://management.azure.com{search_resource_id}"
        f"/sharedPrivateLinkResources/{PRIVATE_LINK_NAME}?api-version=2025-05-01"
    )

    for attempt in range(1, max_attempts + 1):
        connections = run_az(
            "network", "private-endpoint-connection", "list", "--id", cosmos_resource_id
        )
        search_connections = search_private_link_connections(connections)
        if len(search_connections) > 1:
            raise SearchConfigurationError(
                "The POC-owned Cosmos account has multiple Search-managed "
                "private endpoint connections."
            )
        if search_connections:
            connection = search_connections[0]
            state = connection["properties"]["privateLinkServiceConnectionState"]["status"]
            if state == "Rejected":
                raise SearchConfigurationError(
                    "The Search-to-Cosmos private endpoint was rejected."
                )
            if state == "Pending":
                run_az(
                    "network",
                    "private-endpoint-connection",
                    "approve",
                    "--id",
                    connection["id"],
                    "--description",
                    "Approved for the TJX retail Search indexer.",
                )

        shared_link = run_az("rest", "--method", "get", "--uri", shared_link_url)
        properties = shared_link.get("properties", {})
        if (
            properties.get("provisioningState") == "Succeeded"
            and properties.get("status") == "Approved"
        ):
            print(f"PASS: sharedPrivateLinkResources/{PRIVATE_LINK_NAME} (Approved)")
            return

        if attempt < max_attempts:
            print(f"WAIT: Search-to-Cosmos private link approval ({attempt}/{max_attempts})")
            time.sleep(delay_seconds)

    raise SearchConfigurationError("Search-to-Cosmos private link approval timed out.")


def parse_args() -> argparse.Namespace:
    """Parse plan, read-only validation, or explicit apply mode."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "validate", "apply"), default="plan", nargs="?")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser.parse_args()


def main() -> int:
    """Expand and process the declarative Search object graph in dependency order."""
    args = parse_args()
    try:
        config = expand_environment(json.loads(args.config.read_text(encoding="utf-8")))
        objects = config["objects"]
        if args.command == "apply":
            wait_for_cosmos_private_link()
        for item in objects:
            if args.command == "plan":
                print(f"PLAN: PUT {item['kind']}/{item['name']}")
                continue
            method = "PUT" if args.command == "apply" else "GET"
            if args.command == "apply" and item.get("createOnly"):
                current_status = request(
                    config["searchEndpoint"], config["apiVersion"], item, "GET"
                )
                if current_status == 200:
                    print(f"PRESERVE: {item['kind']}/{item['name']} (already exists)")
                    continue
            status = request(config["searchEndpoint"], config["apiVersion"], item, method)
            expected = {200, 201, 204} if method == "PUT" else {200}
            result = "PASS" if status in expected else "MISSING"
            print(f"{result}: {item['kind']}/{item['name']} (HTTP {status})")

        if args.command == "apply":
            print("Applied the complete POC-owned Search object graph.")
        return 0
    except (SearchConfigurationError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
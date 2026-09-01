"""Show or switch the Search alias among baseline and enriched indexes."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from typing import Any

from scripts.manage_search_objects import SearchConfigurationError, run_az

API_VERSION = "2026-04-01"
ALIAS_NAME = "tjx-bvx-products-active"
VARIANTS = {
    "baseline": "tjx-bvx-products-baseline-v1",
    "enriched": "tjx-bvx-products-enriched-v2",
    "normalized": "tjx-bvx-products-enriched-v3",
    "multimodal": "tjx-bvx-products-enriched-v4",
}


def alias_request(endpoint: str, method: str, indexes: list[str] | None = None) -> Any:
    token = run_az("account", "get-access-token", "--resource", "https://search.azure.com")[
        "accessToken"
    ]
    body = None
    if indexes is not None:
        body = json.dumps({"name": ALIAS_NAME, "indexes": indexes}).encode("utf-8")
    request = urllib.request.Request(
        f"{endpoint.rstrip('/')}/aliases/{ALIAS_NAME}?api-version={API_VERSION}",
        method=method,
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read()
            return json.loads(content) if content else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        message = f"Search alias request failed: HTTP {exc.code}: {detail}"
        raise SearchConfigurationError(message) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant", choices=("status", *VARIANTS), default="status", nargs="?")
    args = parser.parse_args()
    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", "").rstrip("/")
    if not endpoint:
        raise SystemExit("AZURE_SEARCH_ENDPOINT is required")

    if args.variant != "status":
        alias_request(endpoint, "PUT", [VARIANTS[args.variant]])
    current = alias_request(endpoint, "GET")
    index = current["indexes"][0]
    variant = next((name for name, value in VARIANTS.items() if value == index), "unknown")
    print(json.dumps({"alias": ALIAS_NAME, "variant": variant, "index": index}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
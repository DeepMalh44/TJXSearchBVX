"""Compare identical queries across V1, V2, and V3 Search indexes."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from scripts.manage_search_objects import SearchConfigurationError, run_az

API_VERSION = "2026-04-01"
INDEXES = {
    "baseline": "tjx-bvx-products-baseline-v1",
    "enriched": "tjx-bvx-products-enriched-v2",
    "normalized": "tjx-bvx-products-enriched-v3",
}
SEMANTIC_CONFIGURATION = "tjx-bvx-products-semantic-v3"


def search(
    endpoint: str,
    token: str,
    index: str,
    query: str,
    top: int,
    semantic: bool = False,
) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {
        "search": query,
        "top": top,
        "select": "id,name,description,category,imageUrl",
        "vectorQueries": [
            {
                "kind": "text",
                "text": query,
                "fields": "descriptionVector",
                "k": top,
            }
        ],
    }
    if semantic:
        payload.update(
            {
                "queryType": "semantic",
                "semanticConfiguration": SEMANTIC_CONFIGURATION,
            }
        )
    encoded_index = urllib.parse.quote(index, safe="")
    request = urllib.request.Request(
        f"{endpoint}/indexes/{encoded_index}/docs/search?api-version={API_VERSION}",
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            rows = json.load(response)["value"]
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SearchConfigurationError(
            f"Search evaluation failed for {index}: HTTP {exc.code}: {detail}"
        ) from exc
    return [
        {
            "id": row["id"],
            "name": row.get("name", ""),
            "score": row.get("@search.score"),
            "rerankerScore": row.get("@search.rerankerScore"),
        }
        for row in rows
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queries", nargs="+", help="Queries to run against every variant")
    parser.add_argument("--top", type=int, default=5, choices=range(1, 25))
    args = parser.parse_args()
    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", "").rstrip("/")
    if not endpoint:
        raise SystemExit("AZURE_SEARCH_ENDPOINT is required")
    token = run_az("account", "get-access-token", "--resource", "https://search.azure.com")[
        "accessToken"
    ]
    report: list[dict[str, Any]] = []
    for query in args.queries:
        variants = {
            name: search(endpoint, token, index, query, args.top)
            for name, index in INDEXES.items()
        }
        variants["normalizedSemantic"] = search(
            endpoint,
            token,
            INDEXES["normalized"],
            query,
            args.top,
            semantic=True,
        )
        report.append({"query": query, "variants": variants})
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
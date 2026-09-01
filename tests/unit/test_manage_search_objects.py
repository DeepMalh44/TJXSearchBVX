from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.manage_search_objects import (
    SearchConfigurationError,
    expand_environment,
    search_private_link_connections,
)


def test_expand_environment_resolves_nested_values(monkeypatch):
    monkeypatch.setenv("AZURE_SEARCH_ENDPOINT", "https://search.example")

    expanded = expand_environment(
        {"endpoint": "${AZURE_SEARCH_ENDPOINT}", "items": ["prefix-${AZURE_SEARCH_ENDPOINT}"]}
    )

    assert expanded == {
        "endpoint": "https://search.example",
        "items": ["prefix-https://search.example"],
    }


def test_expand_environment_rejects_missing_values(monkeypatch):
    monkeypatch.delenv("AZURE_MISSING", raising=False)

    with pytest.raises(SearchConfigurationError, match="AZURE_MISSING"):
        expand_environment("${AZURE_MISSING}")


def test_expand_environment_preserves_numeric_types(monkeypatch):
    monkeypatch.setenv("AZURE_EMBEDDING_DIMENSIONS", "1536")

    assert expand_environment("${AZURE_EMBEDDING_DIMENSIONS}") == 1536


def test_search_private_link_connections_ignores_application_endpoint():
    connections = [
        {
            "properties": {
                "privateEndpoint": {
                    "id": "/subscriptions/app/resourceGroups/app/providers/"
                    "Microsoft.Network/privateEndpoints/pe-cosmos-app"
                }
            }
        },
        {
            "properties": {
                "privateEndpoint": {
                    "id": "/subscriptions/search/resourceGroups/managed/providers/"
                    "Microsoft.Network/privateEndpoints/cosmos-products"
                }
            }
        },
    ]

    assert search_private_link_connections(connections) == [connections[1]]


def test_v4_indexer_includes_metadata_only_products():
    root = Path(__file__).resolve().parents[2]
    objects = json.loads((root / "config" / "search-objects.json").read_text())["objects"]
    objects_by_name = {item["name"]: item["payload"] for item in objects}

    data_source = objects_by_name["tjx-bvx-cosmos-products-ds-v4"]
    indexer = objects_by_name["tjx-bvx-products-enriched-indexer-v4"]

    assert data_source["container"]["query"] == (
        "SELECT * FROM c WHERE c._ts >= @HighWaterMark ORDER BY c._ts"
    )
    assert indexer["dataSourceName"] == data_source["name"]
    assert indexer["parameters"]["configuration"] == {
        "executionEnvironment": "private",
        "assumeOrderByHighWaterMarkColumn": True,
    }
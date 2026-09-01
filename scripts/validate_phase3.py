"""Static, cloud-read-only validation for Phase 3 preparation."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "app/api/main.py",
    "app/api/auth.py",
    "app/api/services.py",
    "app/frontend/package-lock.json",
    "app/static/index.html",
    "app/ingestion/run.py",
    "app/Dockerfile",
    ".dockerignore",
    "infra/modules/phase3.bicep",
    "scripts/configure_entra_app.py",
    "scripts/ensure_subscription_features.py",
    "scripts/upload_source_images.py",
]


def main() -> int:
    errors = [f"missing {path}" for path in REQUIRED if not (ROOT / path).is_file()]
    schema = json.loads((ROOT / "config/search-objects.json").read_text(encoding="utf-8"))
    indexes = [item for item in schema["objects"] if item["kind"] == "indexes"]
    fields = {field["name"] for field in indexes[0]["payload"]["fields"]}
    expected = {"id", "name", "description", "category", "imageUrl", "descriptionVector"}
    if fields != expected:
        errors.append("Search index field contract changed unexpectedly")
    index_names = {item["name"] for item in indexes}
    if index_names != {
        "tjx-bvx-products-baseline-v1",
        "tjx-bvx-products-enriched-v2",
        "tjx-bvx-products-enriched-v3",
        "tjx-bvx-products-enriched-v4",
    }:
        errors.append("Search versioned index contract changed unexpectedly")
    v3 = next(
        (item for item in indexes if item["name"] == "tjx-bvx-products-enriched-v3"),
        None,
    )
    expected_v3_fields = {
        "id",
        "name",
        "description",
        "category",
        "imageUrl",
        "searchText",
        "productFamily",
        "productType",
        "audiences",
        "primaryColors",
        "materials",
        "styles",
        "closureTypes",
        "patterns",
        "occasions",
        "normalizedBrand",
        "attributes",
        "enrichmentConfidence",
        "descriptionVector",
    }
    if v3 is None or {field["name"] for field in v3["payload"]["fields"]} != expected_v3_fields:
        errors.append("Search V3 normalized field contract is incomplete")
    v4 = next(
        (item for item in indexes if item["name"] == "tjx-bvx-products-enriched-v4"),
        None,
    )
    expected_v4_fields = expected_v3_fields | {"imageVector"}
    if v4 is None or {field["name"] for field in v4["payload"]["fields"]} != expected_v4_fields:
        errors.append("Search V4 multimodal field contract is incomplete")
    elif next(
        field for field in v4["payload"]["fields"] if field["name"] == "imageVector"
    ).get("dimensions") != 1024:
        errors.append("Search V4 imageVector must have 1024 dimensions")
    elif next(
        field for field in v4["payload"]["fields"] if field["name"] == "imageVector"
    ).get("vectorSearchProfile") != "tjx-bvx-image-vector-profile":
        errors.append("Search V4 imageVector profile is incorrect")

    object_names = {item["name"] for item in schema["objects"]}
    for required_object in (
        "tjx-bvx-products-enriched-skillset-v4",
        "tjx-bvx-products-enriched-indexer-v4",
    ):
        if required_object not in object_names:
            errors.append(f"missing Search V4 object: {required_object}")
    v4_skillset = next(
        (
            item
            for item in schema["objects"]
            if item["name"] == "tjx-bvx-products-enriched-skillset-v4"
        ),
        None,
    )
    if v4_skillset is not None:
        skill_outputs = {
            output["targetName"]
            for skill in v4_skillset["payload"]["skills"]
            for output in skill["outputs"]
        }
        if not {"descriptionVector", "imageVector"}.issubset(skill_outputs):
            errors.append("Search V4 skillset dual-vector outputs are incomplete")
    v4_indexer = next(
        (
            item
            for item in schema["objects"]
            if item["name"] == "tjx-bvx-products-enriched-indexer-v4"
        ),
        None,
    )
    if v4_indexer is not None:
        indexer_targets = {
            mapping["targetFieldName"]
            for mapping in v4_indexer["payload"]["outputFieldMappings"]
        }
        if not {"descriptionVector", "imageVector"}.issubset(indexer_targets):
            errors.append("Search V4 indexer dual-vector mappings are incomplete")
    bicep = (ROOT / "infra/modules/phase3.bicep").read_text(encoding="utf-8")
    for marker in ("adminUserEnabled: false", "triggerType: 'Manual'", "minReplicas: 0"):
        if marker not in bicep:
            errors.append(f"missing Bicep marker: {marker}")
    azure_yaml = (ROOT / "azure.yaml").read_text(encoding="utf-8")
    if "scripts/ensure_subscription_features.py" not in azure_yaml:
        errors.append("missing subscription feature preprovision hook")
    if errors:
        print("\n".join(f"FAIL: {error}" for error in errors), file=sys.stderr)
        return 1
    print("PASS: Phase 3 static preparation contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

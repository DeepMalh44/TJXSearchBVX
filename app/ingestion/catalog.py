"""Stable source-image mapping and Cosmos document construction."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

IMAGE_SUFFIXES = {".avif", ".jpg", ".jpeg", ".png", ".webp"}
CATEGORY_TERMS = {
    "bag": "Handbags",
    "dress": "Apparel",
    "shoe": "Footwear",
    "boot": "Footwear",
    "shirt": "Apparel",
    "jacket": "Apparel",
    "watch": "Accessories",
}
METADATA_ONLY_PRODUCTS = (
    ("synthetic-wht-m-sndl-slipon", "WHT M SNDL SLIPON", "", "FTWR"),
    ("synthetic-blk-m-sndl", "BLK M SNDL", "MENS SANDAL BLK", "FTWR"),
    ("synthetic-wht-wmn-pump", "WHT WMN PUMP", "DRESS SHOE", "FTWR"),
    ("synthetic-tan-m-loafer-slipon", "TAN M LOAFER SLIPON", "", "FTWR"),
    ("synthetic-blk-xbody-bag", "BLK XBODY BAG", "SMALL CROSS BODY", "HDBGS"),
    ("synthetic-wht-drs-wmn", "WHT DRS WMN", "WOMENS APPAREL", "APRL"),
    ("synthetic-rd-wmn-sndl", "RD WMN SNDL", "", "FTWR"),
    ("synthetic-nvy-m-sneakr", "NVY M SNEAKR", "ATHLETIC", "FTWR"),
)


def source_images(directory: Path) -> list[Path]:
    """Return supported bundled images in deterministic filename order."""
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.casefold() in IMAGE_SUFFIXES
        ),
        key=lambda path: path.name.casefold(),
    )


def stable_identity(path: Path) -> tuple[str, str]:
    """Derive repeatable product and Blob IDs so ingestion is idempotent."""
    normalized = path.name.casefold().encode("utf-8")
    digest = hashlib.sha256(normalized).hexdigest()[:16]
    return f"product-{digest}", f"product-{digest}{path.suffix.casefold()}"


def synthetic_metadata(path: Path) -> dict[str, Any]:
    """Create minimal POC source metadata from a bundled image filename."""
    words = re.findall(r"[a-z0-9]+", path.stem.casefold())
    category = next(
        (value for term, value in CATEGORY_TERMS.items() if term in words),
        "General Merchandise",
    )
    display_name = " ".join(word.capitalize() for word in words) or "Retail Product"
    return {
        "name": display_name,
        "category": category,
        "synthetic": True,
        "syntheticFields": ["name", "category"],
        "sourceFileName": path.name,
    }


def build_document(path: Path, enrichment: dict[str, Any]) -> dict[str, Any]:
    """Build the Cosmos source document; richer taxonomy is added later by Search."""
    product_id, blob_name = stable_identity(path)
    synthetic = synthetic_metadata(path)
    description = str(enrichment["description"]).strip()
    if not description:
        raise ValueError("Vision enrichment returned an empty description")
    return {
        "id": product_id,
        "name": synthetic["name"],
        "description": description,
        "category": synthetic["category"],
        "imageUrl": blob_name,
        **synthetic,
        "vision": {
            "colors": enrichment.get("colors", []),
            "materials": enrichment.get("materials", []),
            "attributes": enrichment.get("attributes", []),
        },
    }


def metadata_only_documents() -> list[dict[str, Any]]:
    """Create coded fixtures used to demonstrate model-based metadata normalization."""
    return [
        {
            "id": product_id,
            "name": coded_name,
            "description": coded_description,
            "category": coded_category,
            "imageUrl": "",
            "sourceFileName": coded_name,
            "synthetic": True,
            "syntheticFields": ["name", "description", "category"],
            "recordType": "metadata-only",
            "schemaVersion": 1,
        }
        for product_id, coded_name, coded_description, coded_category in METADATA_ONLY_PRODUCTS
    ]

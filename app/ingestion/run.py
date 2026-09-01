"""One-shot deterministic Blob, vision, and Cosmos ingestion command."""

from __future__ import annotations

import base64
import io
import json
import mimetypes
import sys
from pathlib import Path
from typing import Any

from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.storage.blob import BlobServiceClient
from openai import OpenAI
from PIL import Image

from app.api.settings import get_settings
from app.ingestion.catalog import (
    build_document,
    metadata_only_documents,
    source_images,
    stable_identity,
)

VISION_SCHEMA = {
    "name": "retail_product",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "description": {"type": "string"},
            "colors": {"type": "array", "items": {"type": "string"}},
            "materials": {"type": "array", "items": {"type": "string"}},
            "attributes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["description", "colors", "materials", "attributes"],
        "additionalProperties": False,
    },
}


def enrich(client: OpenAI, deployment: str, path: Path) -> dict[str, Any]:
    """Extract only visible source facts before the document is written to Cosmos."""
    content_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    content = path.read_bytes()
    if path.suffix.casefold() == ".avif":
        converted = io.BytesIO()
        with Image.open(io.BytesIO(content)) as image:
            image.convert("RGB").save(converted, format="JPEG", quality=90)
        content = converted.getvalue()
        content_type = "image/jpeg"
    encoded = base64.b64encode(content).decode("ascii")
    response = client.chat.completions.create(
        model=deployment,
        response_format={"type": "json_schema", "json_schema": VISION_SCHEMA},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Describe only visible retail product facts. Do not infer brand, "
                            "price, gender, or provenance."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{content_type};base64,{encoded}"},
                    },
                ],
            }
        ],
    )
    return json.loads(response.choices[0].message.content or "{}")


def main() -> int:
    """Upload private images and idempotently seed 31 source-of-truth Cosmos records."""
    settings = get_settings()
    credential = DefaultAzureCredential(
        managed_identity_client_id=settings.managed_identity_client_id
    )
    blobs = BlobServiceClient(
        settings.azure_blob_endpoint, credential=credential
    ).get_container_client(settings.azure_blob_container_name)
    cosmos = (
        CosmosClient(settings.azure_cosmos_endpoint, credential=credential)
        .get_database_client(settings.azure_cosmos_database)
        .get_container_client(settings.azure_cosmos_container)
    )
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )
    vision = OpenAI(
        base_url=f"{settings.azure_openai_endpoint.rstrip('/')}/openai/v1/",
        api_key=token_provider,
    )

    sources = source_images(Path(__file__).resolve().parents[1] / "source-images")
    if len(sources) != 23:
        print(f"ERROR: expected exactly 23 bundled images, found {len(sources)}", file=sys.stderr)
        return 2
    failures = 0
    for position, path in enumerate(sources, start=1):
        _, blob_name = stable_identity(path)
        try:
            blobs.upload_blob(
                blob_name,
                path.read_bytes(),
                overwrite=True,
                metadata={"sourcefilename": path.name},
            )
            document = build_document(
                path, enrich(vision, settings.azure_openai_vision_deployment, path)
            )
            cosmos.upsert_item(document)
            print(f"PASS {position:02d}/23 {path.name} -> {document['id']}")
        except Exception as exc:
            failures += 1
            print(f"FAIL {position:02d}/23 {path.name}: {exc}", file=sys.stderr)
    metadata_documents = metadata_only_documents()
    for position, document in enumerate(metadata_documents, start=1):
        try:
            cosmos.upsert_item(document)
            print(
                f"PASS META {position:02d}/{len(metadata_documents):02d} "
                f"{document['name']} -> {document['id']}"
            )
        except Exception as exc:
            failures += 1
            print(
                f"FAIL META {position:02d}/{len(metadata_documents):02d} "
                f"{document['name']}: {exc}",
                file=sys.stderr,
            )
    total = len(sources) + len(metadata_documents)
    print(f"SUMMARY: {total - failures} succeeded, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Upload the approved local source set with Entra authentication and stable blob names."""

from __future__ import annotations

import argparse
import mimetypes
from pathlib import Path

from azure.identity import AzureCliCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.ingestion.catalog import source_images, stable_identity


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(r"C:\temp\Ketaanh\TJX"))
    parser.add_argument("--blob-endpoint", required=True)
    parser.add_argument("--container", default="product-images")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    images = source_images(args.source)
    if len(images) != 23:
        raise SystemExit(f"Expected exactly 23 source images, found {len(images)}")
    container = None
    if not args.dry_run:
        container = BlobServiceClient(
            args.blob_endpoint, credential=AzureCliCredential()
        ).get_container_client(args.container)
    for path in images:
        _, blob_name = stable_identity(path)
        print(f"{'PLAN' if args.dry_run else 'UPLOAD'}: {path.name} -> {blob_name}")
        if container:
            container.upload_blob(
                blob_name,
                path.read_bytes(),
                overwrite=True,
                metadata={"sourcefilename": path.name},
                content_settings=ContentSettings(
                    content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                ),
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

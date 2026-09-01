from pathlib import Path

from app.ingestion.catalog import (
    build_document,
    metadata_only_documents,
    source_images,
    stable_identity,
    synthetic_metadata,
)


def test_source_images_includes_avif_and_excludes_other_files(tmp_path: Path) -> None:
    (tmp_path / "first.AVIF").touch()
    (tmp_path / "second.jpg").touch()
    (tmp_path / "notes.txt").touch()

    assert [path.name for path in source_images(tmp_path)] == ["first.AVIF", "second.jpg"]


def test_stable_identity_is_case_insensitive_and_preserves_extension() -> None:
    first = stable_identity(Path("Red Bag.JPG"))
    second = stable_identity(Path("red bag.jpg"))

    assert first == second
    assert first[0].startswith("product-")
    assert first[1].endswith(".jpg")


def test_document_matches_search_projection_and_marks_synthetic_fields() -> None:
    document = build_document(
        Path("red leather bag.jpg"),
        {
            "description": "A red leather shoulder bag.",
            "colors": ["red"],
            "materials": ["leather"],
            "attributes": [],
        },
    )

    assert {"id", "name", "description", "category", "imageUrl"} <= document.keys()
    assert document["synthetic"] is True
    assert document["syntheticFields"] == ["name", "category"]
    assert synthetic_metadata(Path("unknown-item.png"))["category"] == "General Merchandise"


def test_metadata_only_documents_are_deterministic_and_keep_partition_key() -> None:
    documents = metadata_only_documents()

    assert len(documents) == 8
    assert len({document["id"] for document in documents}) == len(documents)
    assert all(document["category"] for document in documents)
    assert all(document["imageUrl"] == "" for document in documents)
    assert all(document["recordType"] == "metadata-only" for document in documents)
    assert any(document["description"] == "" for document in documents)
    assert documents[0]["name"] == "WHT M SNDL SLIPON"

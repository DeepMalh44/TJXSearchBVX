import pytest
from pydantic import ValidationError

from app.api.models import (
    CANONICAL_PRODUCT_FAMILIES,
    QueryIntent,
    SearchMode,
    SearchRequest,
    SkillOutput,
    SkillResponse,
    SkillResult,
)


def test_search_request_normalizes_and_bounds_input() -> None:
    request = SearchRequest(query="  red   leather bag  ", mode="hybrid", top=24)

    assert request.query == "red leather bag"
    assert request.mode is SearchMode.HYBRID
    assert request.top == 24


@pytest.mark.parametrize(
    ("query", "top"),
    [(" ", 12), ("valid", 0), ("valid", 25), ("x" * 201, 12)],
)
def test_search_request_rejects_invalid_input(query: str, top: int) -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query=query, top=top)


def test_query_intent_rejects_unknown_or_oversized_model_output() -> None:
    with pytest.raises(ValidationError):
        QueryIntent(searchText="bag", rawOData="productType eq 'bag'")
    with pytest.raises(ValidationError):
        QueryIntent(searchText="bag", attributes=["x" * 81])


def test_skill_response_uses_search_contract_field_names() -> None:
    response = SkillResponse(
        values=[
            SkillResult(
                recordId="1",
                data=SkillOutput(
                    description="White flat sandals",
                    productFamily="footwear",
                    productType="sandals",
                    audiences=["men"],
                    primaryColors=["white"],
                    materials=["synthetic"],
                    styles=["casual"],
                    closureTypes=["slip-on"],
                    patterns=["solid"],
                    occasions=["beach"],
                    normalizedBrand="",
                    attributes=["flat", "open toe"],
                    searchText="white flat sandals shoes footwear",
                    enrichmentConfidence=0.94,
                ),
            )
        ]
    )

    data = response.model_dump()["values"][0]["data"]
    assert data["productFamily"] == "footwear"
    assert data["productType"] == "sandals"
    assert data["audiences"] == ["men"]
    assert data["imageVector"] is None


@pytest.mark.parametrize("vector", [[0.1] * 1023, [float("nan")] * 1024])
def test_skill_output_rejects_invalid_image_vector(vector: list[float]) -> None:
    with pytest.raises(ValidationError, match="imageVector"):
        SkillOutput(
            description="White flat sandals",
            productFamily="footwear",
            productType="sandals",
            audiences=[],
            primaryColors=["white"],
            materials=[],
            styles=[],
            closureTypes=[],
            patterns=[],
            occasions=[],
            normalizedBrand="",
            attributes=[],
            searchText="white flat sandals",
            enrichmentConfidence=0.9,
            imageVector=vector,
        )


@pytest.mark.parametrize(
    ("enriched", "expected"),
    [
        ("handbags", "bag"),
        ("handbag", "bag"),
        ("bags", "bag"),
        ("wallets", "wallet"),
        ("shoes", "footwear"),
        ("outerwear", "apparel"),
        ("dress", "apparel"),
        ("Handbags", "bag"),
        ("footwear", "footwear"),
        ("something unmapped", "general merchandise"),
    ],
)
def test_skill_output_coerces_product_family_to_canonical_taxonomy(
    enriched: str, expected: str
) -> None:
    """Indexed families must match the canonical values query intent can emit."""
    output = SkillOutput(
        description="A product",
        productFamily=enriched,
        productType="tote bag",
        audiences=[],
        primaryColors=[],
        materials=[],
        styles=[],
        closureTypes=[],
        patterns=[],
        occasions=[],
        normalizedBrand="",
        attributes=[],
        searchText="a product",
        enrichmentConfidence=0.9,
    )

    assert output.productFamily == expected
    assert output.productFamily in CANONICAL_PRODUCT_FAMILIES

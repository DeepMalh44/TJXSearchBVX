"""Bounded API request and response contracts."""

import base64
from enum import StrEnum
from math import isfinite

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

MAX_QUERY_IMAGE_BYTES = 4 * 1024 * 1024
QUERY_IMAGE_PREFIXES = (
    "data:image/jpeg;base64,",
    "data:image/png;base64,",
    "data:image/webp;base64,",
)
VALUE_ALIASES = {
    "productFamilies": {"bags": "bag", "handbag": "bag", "handbags": "bag"},
    "productTypes": {
        "sandal": "sandals",
        "pump": "pumps",
        "sneaker": "sneakers",
        "slip on shoe": "slip-on shoe",
        "slip on shoes": "slip-on shoes",
    },
    "audiences": {
        "man": "men",
        "male": "men",
        "mens": "men",
        "men's": "men",
        "woman": "women",
        "female": "women",
        "womens": "women",
        "women's": "women",
    },
    "styles": {"slip on": "slip-on", "slipon": "slip-on"},
    "closureTypes": {"slip on": "slip-on", "slipon": "slip-on"},
}
VALUE_EXPANSIONS = {
    "primaryColors": {
        "dark": ["black", "navy", "brown", "gray"],
        "light": ["white", "cream", "beige", "pastel"],
    }
}
CANONICAL_PRODUCT_FAMILIES = {
    "accessories",
    "apparel",
    "bag",
    "footwear",
    "general merchandise",
    "wallet",
}


def normalize_catalog_values(values: list[str], field_name: str) -> list[str]:
    """Normalize model output before it can participate in exact Search filters."""
    aliases = VALUE_ALIASES.get(field_name, {})
    normalized = [" ".join(value.split()).casefold() for value in values]
    normalized = [aliases.get(value, value) for value in normalized]
    expansions = VALUE_EXPANSIONS.get(field_name, {})
    normalized = [item for value in normalized for item in expansions.get(value, [value])]
    if any(len(value) > 80 for value in normalized):
        raise ValueError("catalog values cannot exceed 80 characters")
    return list(dict.fromkeys(value for value in normalized if value))


class SearchMode(StrEnum):
    KEYWORD = "keyword"
    VECTOR = "vector"
    HYBRID = "hybrid"
    SEMANTIC = "semantic"
    IMAGE = "image"
    COMBINED = "combined"


class SearchRequest(BaseModel):
    """Bounded public search request for text, image, or combined retrieval."""

    model_config = ConfigDict(populate_by_name=True)

    query: str = Field(default="", max_length=200)
    mode: SearchMode = SearchMode.HYBRID
    top: int = Field(default=12, ge=1, le=24)
    image_data_url: str | None = Field(
        default=None,
        alias="imageDataUrl",
        max_length=MAX_QUERY_IMAGE_BYTES * 2,
    )

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = " ".join(value.split())
        return normalized

    @field_validator("image_data_url")
    @classmethod
    def validate_image_data_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        prefix = next((item for item in QUERY_IMAGE_PREFIXES if value.startswith(item)), None)
        if prefix is None:
            raise ValueError("image must be a JPEG, PNG, or WebP data URL")
        try:
            content = base64.b64decode(value[len(prefix) :], validate=True)
        except ValueError as exc:
            raise ValueError("image data must be valid base64") from exc
        if not content or len(content) > MAX_QUERY_IMAGE_BYTES:
            raise ValueError("image must be between 1 byte and 4 MiB")
        return value

    @model_validator(mode="after")
    def validate_mode_inputs(self) -> "SearchRequest":
        image_mode = self.mode in {SearchMode.IMAGE, SearchMode.COMBINED}
        if image_mode and self.image_data_url is None:
            raise ValueError(f"{self.mode.value} mode requires an image")
        if self.mode is SearchMode.COMBINED and not self.query:
            raise ValueError("combined mode requires a text query")
        if not image_mode and not self.query:
            raise ValueError("query must contain non-whitespace characters")
        return self


class ProductResult(BaseModel):
    id: str
    name: str
    description: str
    category: str
    image_url: str | None
    score: float | None = None


class SearchDiagnostics(BaseModel):
    mode: SearchMode
    count: int
    elapsed_ms: int


class SearchResponse(BaseModel):
    results: list[ProductResult]
    diagnostics: SearchDiagnostics


class QueryIntent(BaseModel):
    """Validated model output used to build ranking text and allowlisted filters."""

    model_config = ConfigDict(extra="forbid")

    searchText: str = Field(min_length=1, max_length=200)
    productFamilies: list[str] = Field(default_factory=list, max_length=8)
    productTypes: list[str] = Field(default_factory=list, max_length=8)
    audiences: list[str] = Field(default_factory=list, max_length=8)
    primaryColors: list[str] = Field(default_factory=list, max_length=8)
    materials: list[str] = Field(default_factory=list, max_length=8)
    styles: list[str] = Field(default_factory=list, max_length=8)
    closureTypes: list[str] = Field(default_factory=list, max_length=8)
    patterns: list[str] = Field(default_factory=list, max_length=8)
    occasions: list[str] = Field(default_factory=list, max_length=8)
    normalizedBrands: list[str] = Field(default_factory=list, max_length=8)
    attributes: list[str] = Field(default_factory=list, max_length=8)
    excludedProductFamilies: list[str] = Field(default_factory=list, max_length=8)
    excludedProductTypes: list[str] = Field(default_factory=list, max_length=8)
    excludedAudiences: list[str] = Field(default_factory=list, max_length=8)
    excludedPrimaryColors: list[str] = Field(default_factory=list, max_length=8)
    excludedMaterials: list[str] = Field(default_factory=list, max_length=8)
    excludedNormalizedBrands: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("searchText")
    @classmethod
    def normalize_search_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("searchText must contain non-whitespace characters")
        return normalized

    @field_validator(
        "productFamilies",
        "productTypes",
        "audiences",
        "primaryColors",
        "materials",
        "styles",
        "closureTypes",
        "patterns",
        "occasions",
        "normalizedBrands",
        "attributes",
        "excludedProductFamilies",
        "excludedProductTypes",
        "excludedAudiences",
        "excludedPrimaryColors",
        "excludedMaterials",
        "excludedNormalizedBrands",
    )
    @classmethod
    def normalize_values(cls, values: list[str], info: ValidationInfo) -> list[str]:
        field_name = info.field_name.removeprefix("excluded")
        field_name = field_name[0].lower() + field_name[1:]
        normalized = normalize_catalog_values(values, field_name)
        if field_name == "productFamilies" and any(
            value not in CANONICAL_PRODUCT_FAMILIES for value in normalized
        ):
            raise ValueError("product families must use the canonical search taxonomy")
        return normalized


class SkillInput(BaseModel):
    imageUrl: str = ""
    name: str = ""
    category: str = ""


class SkillRecord(BaseModel):
    recordId: str
    data: SkillInput


class SkillRequest(BaseModel):
    """Azure AI Search custom Web API skill batch contract."""

    values: list[SkillRecord] = Field(min_length=1, max_length=10)


class SkillOutput(BaseModel):
    """Derived fields returned to the indexer and stored only in Azure AI Search."""

    description: str
    productFamily: str
    productType: str
    audiences: list[str]
    primaryColors: list[str]
    materials: list[str]
    styles: list[str]
    closureTypes: list[str]
    patterns: list[str]
    occasions: list[str]
    normalizedBrand: str
    attributes: list[str]
    searchText: str
    enrichmentConfidence: float = Field(ge=0, le=1)
    imageVector: list[float] | None = Field(default=None, max_length=1024)

    @field_validator("imageVector")
    @classmethod
    def validate_image_vector(cls, value: list[float] | None) -> list[float] | None:
        if value is not None and len(value) != 1024:
            raise ValueError("imageVector must contain exactly 1024 values")
        if value is not None and not all(isfinite(item) for item in value):
            raise ValueError("imageVector values must be finite")
        return value

    @field_validator("productFamily", "productType")
    @classmethod
    def normalize_scalar_taxonomy(cls, value: str, info: ValidationInfo) -> str:
        normalized = normalize_catalog_values([value], f"{info.field_name}s")
        return normalized[0] if normalized else ""

    @field_validator(
        "audiences",
        "primaryColors",
        "materials",
        "styles",
        "closureTypes",
        "patterns",
        "occasions",
        "attributes",
    )
    @classmethod
    def normalize_enrichment_values(cls, values: list[str], info: ValidationInfo) -> list[str]:
        return normalize_catalog_values(values, info.field_name)


class SkillResult(BaseModel):
    recordId: str
    data: SkillOutput | None = None
    errors: list[dict[str, str]] | None = None
    warnings: list[dict[str, str]] | None = None


class SkillResponse(BaseModel):
    values: list[SkillResult]

"""Managed-identity service adapters for Search and private Blob access."""

from __future__ import annotations

import base64
import io
import logging
import math
import time
from collections.abc import Iterator
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Any

import httpx
from azure.core.credentials import TokenCredential
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery, VectorizedQuery
from azure.storage.blob import BlobServiceClient
from openai import OpenAI
from PIL import Image

from app.api.models import (
    CANONICAL_PRODUCT_FAMILIES,
    ProductResult,
    QueryIntent,
    SearchDiagnostics,
    SearchMode,
    SearchRequest,
    SearchResponse,
    SkillOutput,
)
from app.api.settings import Settings, get_settings

PRODUCT_ENRICHMENT_SCHEMA = {
    "name": "search_product_enrichment",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "description": {"type": "string"},
            "productFamily": {"type": "string"},
            "productType": {"type": "string"},
            "audiences": {"type": "array", "items": {"type": "string"}},
            "primaryColors": {"type": "array", "items": {"type": "string"}},
            "materials": {"type": "array", "items": {"type": "string"}},
            "styles": {"type": "array", "items": {"type": "string"}},
            "closureTypes": {"type": "array", "items": {"type": "string"}},
            "patterns": {"type": "array", "items": {"type": "string"}},
            "occasions": {"type": "array", "items": {"type": "string"}},
            "normalizedBrand": {"type": "string"},
            "attributes": {"type": "array", "items": {"type": "string"}},
            "searchText": {"type": "string"},
            "enrichmentConfidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [
            "description",
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
            "searchText",
            "enrichmentConfidence",
        ],
        "additionalProperties": False,
    },
}
QUERY_INTENT_FIELDS = (
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
QUERY_INTENT_SCHEMA = {
    "name": "retail_query_intent",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "searchText": {"type": "string", "minLength": 1, "maxLength": 200},
            **{
                field: {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "maxLength": 80,
                        **(
                            {"enum": sorted(CANONICAL_PRODUCT_FAMILIES)}
                            if field in {"productFamilies", "excludedProductFamilies"}
                            else {}
                        ),
                    },
                    "maxItems": 8,
                }
                for field in QUERY_INTENT_FIELDS
            },
        },
        "required": ["searchText", *QUERY_INTENT_FIELDS],
        "additionalProperties": False,
    },
}
logger = logging.getLogger(__name__)

INTENT_FIELD_ADAPTERS = {
    "productFamilies": ("productFamily", False),
    "productTypes": ("productType", False),
    "audiences": ("audiences", True),
    "primaryColors": ("primaryColors", True),
    "materials": ("materials", True),
    "styles": ("styles", True),
    "closureTypes": ("closureTypes", True),
    "patterns": ("patterns", True),
    "occasions": ("occasions", True),
    "normalizedBrands": ("normalizedBrand", False),
    "attributes": ("attributes", True),
}
EXCLUDED_INTENT_FIELD_ADAPTERS = {
    "excludedProductFamilies": ("productFamily", False),
    "excludedProductTypes": ("productType", False),
    "excludedAudiences": ("audiences", True),
    "excludedPrimaryColors": ("primaryColors", True),
    "excludedMaterials": ("materials", True),
    "excludedNormalizedBrands": ("normalizedBrand", False),
}
V2_INTENT_FIELDS = {"productTypes", "primaryColors", "materials", "attributes"}
SEMANTIC_CONFIGURATION_NAME = "tjx-bvx-products-semantic-v3"
MIN_SEMANTIC_RERANKER_SCORE = 2.5
VISION_API_VERSION = "2024-02-01"
VISION_MODEL_VERSION = "2023-04-15"
IMAGE_VECTOR_DIMENSIONS = 1024
GENERIC_PRODUCT_NOUNS = {
    "apparel",
    "clothing",
    "footwear",
    "ons",
    "shoe",
    "shoes",
    "slipons",
}
PRODUCT_TYPE_DESCRIPTORS = {"athletic", "casual", "dress", "on", "slip", "slipon"}
RANKING_ONLY_INTENT_FIELDS = {
    "attributes",
    "closureTypes",
    "occasions",
    "patterns",
    "styles",
}


def is_generic_product_type(value: str) -> bool:
    """Return whether a model-produced type is too broad to use as a hard filter."""
    tokens = set(value.replace("-", " ").split())
    return bool(tokens & GENERIC_PRODUCT_NOUNS) and tokens <= (
        GENERIC_PRODUCT_NOUNS | PRODUCT_TYPE_DESCRIPTORS
    )


def safe_blob_name(value: str) -> str:
    """Accept a single Blob object name and reject paths or traversal attempts."""
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 1 or not path.name:
        raise ValueError("Invalid blob name")
    return path.name


def normalize_image_for_model(content: bytes) -> bytes:
    """Convert supported source images to the JPEG payload expected by model APIs."""
    converted = io.BytesIO()
    with Image.open(io.BytesIO(content)) as image:
        image.convert("RGB").save(converted, format="JPEG", quality=90)
    return converted.getvalue()


def decode_image_data_url(value: str) -> bytes:
    """Decode an image data URL after the request model has validated its format and size."""
    return base64.b64decode(value.split(",", 1)[1], validate=True)


def _odata_string(value: str) -> str:
    return f"'{value.replace(chr(39), chr(39) * 2)}'"


def intent_filter(intent: QueryIntent, supported_fields: set[str] | None = None) -> str | None:
    """Build safe OData from validated facets supported by the current index version.

    Alternatives within one facet use ``or``; separate facets use ``and``. Descriptive
    facets stay in ranking text instead of becoming brittle exact filters. Callers can
    pass an older index's field set when retrying through the stable alias.
    """
    clauses: list[str] = []
    for intent_field, (index_field, is_collection) in INTENT_FIELD_ADAPTERS.items():
        if intent_field in RANKING_ONLY_INTENT_FIELDS:
            continue
        if intent_field == "productTypes" and len(intent.productFamilies) > 1:
            continue
        if supported_fields is not None and intent_field not in supported_fields:
            continue
        values = getattr(intent, intent_field)
        if intent_field == "productTypes":
            values = [value for value in values if not is_generic_product_type(value)]
        if not values:
            continue
        alternatives = []
        for value in values:
            literal = _odata_string(value)
            alternatives.append(
                f"{index_field}/any(item: item eq {literal})"
                if is_collection
                else f"{index_field} eq {literal}"
            )
        clauses.append(f"({' or '.join(alternatives)})")
    for intent_field, (index_field, is_collection) in EXCLUDED_INTENT_FIELD_ADAPTERS.items():
        included_field = intent_field.removeprefix("excluded")
        included_field = included_field[0].lower() + included_field[1:]
        if supported_fields is not None and included_field not in supported_fields:
            continue
        for value in getattr(intent, intent_field):
            literal = _odata_string(value)
            clauses.append(
                f"not {index_field}/any(item: item eq {literal})"
                if is_collection
                else f"{index_field} ne {literal}"
            )
    return " and ".join(clauses) if clauses else None


class AzureServices:
    """Managed-identity adapters for query serving and Search index enrichment.

    Query-time methods understand requests and retrieve products. ``enrich_product`` is
    different: Azure AI Search invokes it as a custom skill while an indexer is running.
    """

    def __init__(self, settings: Settings, credential: TokenCredential) -> None:
        self.settings = settings
        self.credential = credential
        self.http = httpx.Client(timeout=60)
        self.search = SearchClient(
            settings.azure_search_endpoint,
            settings.azure_search_index,
            credential,
        )
        self.blobs = BlobServiceClient(settings.azure_blob_endpoint, credential=credential)
        from azure.identity import get_bearer_token_provider

        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )
        self.vision = OpenAI(
            base_url=f"{settings.azure_openai_endpoint.rstrip('/')}/openai/v1/",
            api_key=token_provider,
        )

    def vectorize_image(self, content: bytes) -> list[float]:
        """Create a validated 1,024-dimensional visual embedding with Azure AI Vision."""
        endpoint = self.settings.azure_ai_vision_endpoint.rstrip("/")
        url = (
            f"{endpoint}/computervision/retrieval:vectorizeImage"
            f"?api-version={VISION_API_VERSION}&model-version={VISION_MODEL_VERSION}"
        )
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                token = self.credential.get_token(
                    "https://cognitiveservices.azure.com/.default"
                ).token
                response = self.http.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/octet-stream",
                    },
                    content=normalize_image_for_model(content),
                )
                response.raise_for_status()
                vector = [float(value) for value in response.json()["vector"]]
                if len(vector) != IMAGE_VECTOR_DIMENSIONS:
                    raise ValueError(
                        f"Azure Vision returned {len(vector)} dimensions; "
                        f"expected {IMAGE_VECTOR_DIMENSIONS}"
                    )
                if not all(math.isfinite(value) for value in vector):
                    raise ValueError("Azure Vision returned a non-finite image vector")
                return vector
            except Exception as exc:
                last_error = exc
                logger.warning("Image vectorization attempt %d failed", attempt, exc_info=True)
        raise RuntimeError("Image vectorization failed after three attempts") from last_error

    def understand_query(self, query: str) -> QueryIntent:
        """Translate free-form query text into validated ranking text and filter facets."""
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = self.vision.chat.completions.create(
                    model=self.settings.azure_openai_vision_deployment,
                    response_format={"type": "json_schema", "json_schema": QUERY_INTENT_SCHEMA},
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Convert retail searches into normalized structured intent. "
                                "Preserve every explicit constraint. Expand abbreviations and "
                                "buyer language into concise lower-case catalog terms. Put only "
                                "constraints supported "
                                "by the schema in the arrays; use empty arrays for unspecified "
                                "dimensions. Product family is canonical and broad: use footwear, "
                                "apparel, bag, wallet, accessories, or general merchandise. "
                                "Product type is specific, such as sandals, pumps, "
                                "dress, or crossbody bag. searchText must retain the meaning of "
                                "the request "
                                "for lexical and vector ranking. Put explicitly negated family, "
                                "type, audience, color, material, or brand constraints only in "
                                "their excluded arrays and omit them from positive arrays. "
                                "Never produce OData."
                            ),
                        },
                        {"role": "user", "content": query},
                    ],
                )
                return QueryIntent.model_validate_json(
                    response.choices[0].message.content or "{}"
                )
            except Exception as exc:
                last_error = exc
                logger.warning("Query understanding attempt %d failed", attempt, exc_info=True)
        raise RuntimeError("Query understanding failed after three attempts") from last_error

    def understand_image_query(self, image_data_url: str, query: str = "") -> QueryIntent:
        """Build intent from an image and optional explicit text constraints.

        In combined mode the image contributes the canonical broad product family and
        ranking language. Other hard-filter facets come only from the user's text.
        """
        instruction = (
            "Convert the primary retail product in this image into normalized structured "
            "search intent. Ignore backgrounds, people, props, and unrelated accessories. "
            "Preserve every explicit text constraint. Use concise lower-case catalog terms, "
            "empty arrays for unsupported dimensions, and never produce OData."
        )
        if query:
            instruction += (
                " Infer only the broad product family from the image for productFamilies. "
                "All other structured arrays must contain only constraints explicitly stated "
                "in the additional text, not properties inferred from the image. Image properties "
                "must still be included in searchText for ranking. Put explicitly negated type, "
                "audience, color, material, or brand constraints only in their excluded "
                f"arrays. Additional search constraints: {query}"
            )
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = self.vision.chat.completions.create(
                    model=self.settings.azure_openai_vision_deployment,
                    response_format={"type": "json_schema", "json_schema": QUERY_INTENT_SCHEMA},
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": instruction},
                                {"type": "image_url", "image_url": {"url": image_data_url}},
                            ],
                        }
                    ],
                )
                return QueryIntent.model_validate_json(
                    response.choices[0].message.content or "{}"
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Image query understanding attempt %d failed", attempt, exc_info=True
                )
        raise RuntimeError("Image query understanding failed after three attempts") from last_error

    def search_products(self, request: SearchRequest) -> SearchResponse:
        """Execute one of the six retrieval modes against the active Search alias.

        Text vectors are generated by the Search vectorizer; image vectors come from
        Azure AI Vision. Structured filters are applied before vector retrieval. If an
        older alias target rejects newer fields, the request retries with its supported
        facets and finally without a filter. This adapts filters only: image modes still
        require V4 and semantic modes require an index with the semantic configuration.
        """
        started = time.perf_counter()
        filter_intent: QueryIntent | None
        if request.mode is SearchMode.COMBINED:
            assert request.image_data_url is not None
            image_vector = self.vectorize_image(decode_image_data_url(request.image_data_url))
            filter_intent = self.understand_image_query(
                request.image_data_url, request.query
            )
            intent = filter_intent
        elif request.mode is SearchMode.IMAGE:
            assert request.image_data_url is not None
            image_vector = self.vectorize_image(decode_image_data_url(request.image_data_url))
            image_intent = self.understand_image_query(request.image_data_url)
            intent = image_intent
            filter_intent = QueryIntent(
                searchText=image_intent.searchText,
                productFamilies=image_intent.productFamilies,
            )
        else:
            image_vector = None
            intent = self.understand_query(request.query)
            filter_intent = intent
        options: dict[str, Any] = {
            "top": request.top,
            "select": ["id", "name", "description", "category", "imageUrl"],
        }
        semantic_modes = {SearchMode.SEMANTIC, SearchMode.COMBINED}
        vector_queries: list[VectorizableTextQuery | VectorizedQuery] = []
        if request.mode in {
            SearchMode.VECTOR,
            SearchMode.HYBRID,
            SearchMode.SEMANTIC,
            SearchMode.COMBINED,
        }:
            vector_queries.append(
                VectorizableTextQuery(
                    text=intent.searchText,
                    k=request.top,
                    fields="descriptionVector",
                )
            )
        if image_vector is not None:
            vector_queries.append(
                VectorizedQuery(vector=image_vector, k=request.top, fields="imageVector")
            )
        if vector_queries:
            options["vector_queries"] = vector_queries
            options["vector_filter_mode"] = "preFilter"
        if request.mode in {SearchMode.KEYWORD, SearchMode.HYBRID, *semantic_modes}:
            options["search_mode"] = "all"
        if request.mode in semantic_modes:
            options["query_type"] = "semantic"
            options["semantic_configuration_name"] = SEMANTIC_CONFIGURATION_NAME
        search_text = (
            intent.searchText
            if request.mode not in {SearchMode.VECTOR, SearchMode.IMAGE}
            else None
        )
        filters = (
            [None]
            if filter_intent is None
            else [
                intent_filter(filter_intent),
                intent_filter(filter_intent, V2_INTENT_FIELDS),
                None,
            ]
        )
        rows = None
        applied_filter: str | None = None
        for product_filter in dict.fromkeys(filters):
            if product_filter:
                options["filter"] = product_filter
            else:
                options.pop("filter", None)
            try:
                rows = list(self.search.search(search_text=search_text, **options))
                applied_filter = product_filter
                break
            except HttpResponseError as exc:
                if product_filter is None or exc.status_code != 400:
                    raise
                logger.info("Active Search index rejected intent filter; trying older adapter")
        assert rows is not None
        # Suppress weak unfiltered semantic neighbors; an explicit filter is already a
        # strong eligibility signal and should not be overridden by this ranking threshold.
        if request.mode in semantic_modes and applied_filter is None:
            rows = [
                row
                for row in rows
                if (row.get("@search.reranker_score") or 0) >= MIN_SEMANTIC_RERANKER_SCORE
            ]
        results = [
            ProductResult(
                id=row["id"],
                name=row.get("name", ""),
                description=row.get("description", ""),
                category=row.get("category", ""),
                image_url=(
                    f"/api/images/{safe_blob_name(row['imageUrl'])}"
                    if row.get("imageUrl")
                    else None
                ),
                score=row.get("@search.reranker_score") or row.get("@search.score"),
            )
            for row in rows
        ]
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return SearchResponse(
            results=results,
            diagnostics=SearchDiagnostics(
                mode=request.mode, count=len(results), elapsed_ms=elapsed_ms
            ),
        )

    def download_image(self, blob_name: str) -> tuple[Iterator[bytes], str]:
        """Stream a private product image through the authenticated API."""
        downloader = self.blobs.get_blob_client(
            self.settings.azure_blob_container_name,
            safe_blob_name(blob_name),
        ).download_blob(max_concurrency=1)
        content_type = (
            downloader.properties.content_settings.content_type or "application/octet-stream"
        )
        return downloader.chunks(), content_type

    def enrich_product(self, image_url: str, name: str, category: str) -> SkillOutput:
        """Produce Search-only taxonomy, text, and image vectors during indexing.

        Cosmos source documents are not mutated. Metadata-only products skip Blob and
        visual-vector work, while image-bearing products are classified using both their
        source metadata and protected Blob content.
        """
        blob_name = safe_blob_name(image_url) if image_url else None
        image_vector: list[float] | None = None
        prompt = (
            "Describe and classify only the primary retail product. Ignore backgrounds, "
            "surfaces, models, hangers, props, and accessories not being sold. Return a "
            "concise product-only description and normalized lower-case retail taxonomy "
            "for product family, product type, audiences, visible or explicitly coded "
            "colors, materials, styles, closure types, patterns, occasions, brand, and "
            "useful attributes. Normalize recognized retail shorthand and source codes "
            "from their catalog context without relying on a retailer-specific codebook. "
            "Do not guess when a token is ambiguous; preserve it in search text instead. "
            "Use a broad, stable retail product family and a specific product type. "
            "Use empty arrays or an empty string when an "
            "attribute is neither visible nor supported by source metadata; do not guess. "
            "Include natural search text with common retail synonyms and a 0-to-1 "
            "confidence for the classification. Source metadata: "
            f"name={name!r}, category={category!r}."
        )
        model_content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if blob_name:
            downloader = self.blobs.get_blob_client(
                self.settings.azure_blob_container_name, blob_name
            ).download_blob(max_concurrency=1)
            content = normalize_image_for_model(downloader.readall())
            image_vector = self.vectorize_image(content)
            encoded = base64.b64encode(content).decode("ascii")
            model_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                }
            )
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = self.vision.chat.completions.create(
                    model=self.settings.azure_openai_vision_deployment,
                    response_format={
                        "type": "json_schema",
                        "json_schema": PRODUCT_ENRICHMENT_SCHEMA,
                    },
                    messages=[
                        {
                            "role": "user",
                            "content": model_content,
                        }
                    ],
                )
                output = SkillOutput.model_validate_json(
                    response.choices[0].message.content or "{}"
                )
                return output.model_copy(update={"imageVector": image_vector})
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Product enrichment attempt %d failed for blob %s",
                    attempt,
                    blob_name or "metadata-only",
                    exc_info=True,
                )
        raise RuntimeError("Product enrichment failed after three attempts") from last_error

    def ready(self) -> None:
        """Fail when the configured active Search alias cannot answer a minimal query."""
        next(iter(self.search.search(search_text="*", top=1, select=["id"])), None)


@lru_cache
def get_services() -> AzureServices:
    """Return one process-wide service adapter backed by the application identity."""
    settings = get_settings()
    credential = DefaultAzureCredential(
        managed_identity_client_id=settings.managed_identity_client_id
    )
    return AzureServices(settings, credential)

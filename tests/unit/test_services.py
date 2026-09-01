import json
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

import app.api.services as services_module
from app.api.models import QueryIntent, SearchMode, SearchRequest
from app.api.services import (
    AzureServices,
    decode_image_data_url,
    intent_filter,
    normalize_image_for_model,
    safe_blob_name,
)


@pytest.mark.parametrize("value", ["../secret.jpg", "folder/image.jpg", "/absolute.jpg", ""])
def test_safe_blob_name_rejects_path_traversal(value: str) -> None:
    with pytest.raises(ValueError):
        safe_blob_name(value)


def test_safe_blob_name_accepts_stable_product_name() -> None:
    assert safe_blob_name("product-0123456789abcdef.jpg") == "product-0123456789abcdef.jpg"


def test_normalize_image_for_model_converts_to_rgb_jpeg() -> None:
    source = BytesIO()
    Image.new("RGBA", (2, 2), (255, 255, 255, 128)).save(source, format="PNG")

    normalized = normalize_image_for_model(source.getvalue())

    with Image.open(BytesIO(normalized)) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"


def test_decode_image_data_url_returns_binary_content() -> None:
    assert decode_image_data_url("data:image/png;base64,aW1hZ2U=") == b"image"


def test_vectorize_image_calls_vision_with_managed_identity() -> None:
    source = BytesIO()
    Image.new("RGB", (2, 2), "white").save(source, format="PNG")

    class HttpClientStub:
        def __init__(self) -> None:
            self.url = ""
            self.options = {}

        def post(self, url, **options):
            self.url = url
            self.options = options
            return SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {"vector": [0.1] * 1024},
            )

    http = HttpClientStub()
    services = object.__new__(AzureServices)
    services.settings = SimpleNamespace(azure_ai_vision_endpoint="https://vision.example/")
    services.credential = SimpleNamespace(
        get_token=lambda scope: SimpleNamespace(token=f"token-for:{scope}")
    )
    services.http = http

    vector = services.vectorize_image(source.getvalue())

    assert len(vector) == 1024
    assert "retrieval:vectorizeImage" in http.url
    assert "api-version=2024-02-01" in http.url
    assert "model-version=2023-04-15" in http.url
    assert http.options["headers"]["Authorization"].startswith("Bearer token-for:")
    assert http.options["headers"]["Content-Type"] == "application/octet-stream"


def test_vectorize_image_rejects_wrong_dimensions_after_retries() -> None:
    source = BytesIO()
    Image.new("RGB", (2, 2), "white").save(source, format="JPEG")
    attempts = 0

    def post(*_args, **_options):
        nonlocal attempts
        attempts += 1
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"vector": [0.1] * 10},
        )

    services = object.__new__(AzureServices)
    services.settings = SimpleNamespace(azure_ai_vision_endpoint="https://vision.example")
    services.credential = SimpleNamespace(get_token=lambda _scope: SimpleNamespace(token="token"))
    services.http = SimpleNamespace(post=post)

    with pytest.raises(RuntimeError, match="after three attempts"):
        services.vectorize_image(source.getvalue())

    assert attempts == 3


def test_keyword_search_requires_all_query_terms() -> None:
    class SearchClientStub:
        def __init__(self) -> None:
            self.options = {}

        def search(self, **options):
            self.options = options
            return []

    client = SearchClientStub()
    services = object.__new__(AzureServices)
    services.search = client
    services.understand_query = lambda _query: QueryIntent(searchText="white dress")

    services.search_products(
        SearchRequest(query="white dress", mode=SearchMode.KEYWORD, top=12)
    )

    assert client.options["search_text"] == "white dress"
    assert client.options["search_mode"] == "all"


def test_hybrid_search_uses_structured_intent_for_ranking_and_filtering() -> None:
    class SearchClientStub:
        def __init__(self) -> None:
            self.options = {}

        def search(self, **options):
            self.options = options
            return []

    client = SearchClientStub()
    services = object.__new__(AzureServices)
    services.search = client
    services.understand_query = lambda _query: QueryIntent(
        searchText="black crossbody bag",
        productFamilies=["bag"],
        productTypes=["crossbody bag"],
        primaryColors=["black"],
    )

    services.search_products(
        SearchRequest(query="something dark I can wear across my body", mode=SearchMode.HYBRID)
    )

    assert client.options["search_text"] == "black crossbody bag"
    assert client.options["search_mode"] == "all"
    assert len(client.options["vector_queries"]) == 1
    assert client.options["vector_queries"][0].text == "black crossbody bag"
    assert client.options["vector_queries"][0].k == 12
    assert client.options["vector_filter_mode"] == "preFilter"
    assert "productFamily eq 'bag'" in client.options["filter"]
    assert "productType eq 'crossbody bag'" in client.options["filter"]
    assert "primaryColors/any(item: item eq 'black')" in client.options["filter"]


def test_semantic_search_uses_hybrid_retrieval_and_v3_semantic_configuration() -> None:
    class SearchClientStub:
        def __init__(self) -> None:
            self.options = {}

        def search(self, **options):
            self.options = options
            return []

    client = SearchClientStub()
    services = object.__new__(AzureServices)
    services.search = client
    services.understand_query = lambda _query: QueryIntent(searchText="casual summer sandals")

    services.search_products(
        SearchRequest(query="something casual for summer", mode=SearchMode.SEMANTIC)
    )

    assert client.options["search_text"] == "casual summer sandals"
    assert client.options["query_type"] == "semantic"
    assert client.options["semantic_configuration_name"] == "tjx-bvx-products-semantic-v3"
    assert len(client.options["vector_queries"]) == 1


def test_semantic_search_discards_results_below_reranker_threshold() -> None:
    class SearchClientStub:
        def search(self, **_options):
            return [
                {
                    "id": "strong",
                    "name": "Strong match",
                    "description": "",
                    "category": "",
                    "@search.reranker_score": 2.5,
                },
                {
                    "id": "weak",
                    "name": "Weak match",
                    "description": "",
                    "category": "",
                    "@search.reranker_score": 2.49,
                },
            ]

    services = object.__new__(AzureServices)
    services.search = SearchClientStub()
    services.understand_query = lambda _query: QueryIntent(searchText="black lace-up shoe")

    response = services.search_products(
        SearchRequest(query="black shoe with white laces", mode=SearchMode.SEMANTIC)
    )

    assert [result.id for result in response.results] == ["strong"]
    assert response.results[0].score == 2.5
    assert response.diagnostics.count == 1


def test_semantic_search_keeps_filtered_results_below_reranker_threshold() -> None:
    class SearchClientStub:
        def search(self, **_options):
            return [
                {
                    "id": "black-sandal",
                    "name": "Black sandal",
                    "description": "",
                    "category": "",
                    "@search.reranker_score": 1.8,
                }
            ]

    services = object.__new__(AzureServices)
    services.search = SearchClientStub()
    services.understand_query = lambda _query: QueryIntent(
        searchText="black purse and sandals",
        productFamilies=["bag", "footwear"],
        productTypes=["purse", "sandals"],
        primaryColors=["black"],
    )

    response = services.search_products(
        SearchRequest(query="blk color purse and sandals", mode=SearchMode.SEMANTIC)
    )

    assert [result.id for result in response.results] == ["black-sandal"]


def test_nonsemantic_search_does_not_apply_reranker_threshold() -> None:
    class SearchClientStub:
        def search(self, **_options):
            return [
                {
                    "id": "keyword-result",
                    "name": "Keyword result",
                    "description": "",
                    "category": "",
                    "@search.score": 0.4,
                }
            ]

    services = object.__new__(AzureServices)
    services.search = SearchClientStub()
    services.understand_query = lambda _query: QueryIntent(searchText="shoe")

    response = services.search_products(SearchRequest(query="shoe", mode=SearchMode.KEYWORD))

    assert [result.id for result in response.results] == ["keyword-result"]


def test_nonsemantic_search_uses_vector_score_when_reranker_score_is_null() -> None:
    class SearchClientStub:
        def search(self, **_options):
            return [
                {
                    "id": "image-result",
                    "name": "Image result",
                    "description": "",
                    "category": "",
                    "@search.score": 0.92,
                    "@search.reranker_score": None,
                }
            ]

    services = object.__new__(AzureServices)
    services.search = SearchClientStub()
    services.vectorize_image = lambda _image: [0.1] * 1024
    services.understand_image_query = lambda _image: QueryIntent(
        searchText="sandals",
        productFamilies=["footwear"],
    )

    response = services.search_products(
        SearchRequest(mode=SearchMode.IMAGE, imageDataUrl="data:image/png;base64,aW1hZ2U=")
    )

    assert response.results[0].score == 0.92


def test_image_search_uses_product_family_filter_and_native_image_vector() -> None:
    class SearchClientStub:
        def __init__(self) -> None:
            self.options = {}

        def search(self, **options):
            self.options = options
            return []

    client = SearchClientStub()
    services = object.__new__(AzureServices)
    services.search = client
    services.vectorize_image = lambda _image: [0.1] * 1024
    services.understand_image_query = lambda _image: QueryIntent(
        searchText="blue striped flip-flop sandals",
        productFamilies=["footwear"],
        productTypes=["sandals"],
        primaryColors=["blue", "white"],
    )

    services.search_products(
        SearchRequest(
            mode=SearchMode.IMAGE,
            imageDataUrl="data:image/png;base64,aW1hZ2U=",
        )
    )

    assert client.options["search_text"] is None
    assert len(client.options["vector_queries"]) == 1
    assert client.options["vector_queries"][0].fields == "imageVector"
    assert len(client.options["vector_queries"][0].vector) == 1024
    assert "query_type" not in client.options
    assert client.options["filter"] == "(productFamily eq 'footwear')"


def test_combined_search_uses_text_and_native_image_vectors() -> None:
    class SearchClientStub:
        def __init__(self) -> None:
            self.options = {}

        def search(self, **options):
            self.options = options
            return []

    client = SearchClientStub()
    services = object.__new__(AzureServices)
    services.search = client
    services.vectorize_image = lambda _image: [0.1] * 1024
    services.understand_image_query = lambda _image, _query: QueryIntent(
        searchText="striped sandals not black",
        productFamilies=["footwear"],
        excludedPrimaryColors=["black"],
    )

    services.search_products(
        SearchRequest(
            query="striped sandals not black",
            mode=SearchMode.COMBINED,
            imageDataUrl="data:image/png;base64,aW1hZ2U=",
        )
    )

    assert client.options["search_text"] == "striped sandals not black"
    assert client.options["query_type"] == "semantic"
    assert [query.fields for query in client.options["vector_queries"]] == [
        "descriptionVector",
        "imageVector",
    ]
    assert client.options["filter"] == (
        "(productFamily eq 'footwear') and "
        "not primaryColors/any(item: item eq 'black')"
    )


def test_search_request_requires_inputs_for_selected_mode() -> None:
    with pytest.raises(ValueError, match="combined mode requires a text query"):
        SearchRequest(mode=SearchMode.COMBINED, imageDataUrl="data:image/png;base64,YQ==")
    with pytest.raises(ValueError, match="requires an image"):
        SearchRequest(query="red", mode=SearchMode.IMAGE)
    with pytest.raises(ValueError, match="non-whitespace"):
        SearchRequest(query="   ", mode=SearchMode.KEYWORD)


def test_intent_filter_escapes_model_values_and_uses_only_whitelisted_fields() -> None:
    product_filter = intent_filter(
        QueryIntent(
            searchText="designer bag",
            productTypes=["women's bag"],
            normalizedBrands=["o'neill"],
        )
    )

    assert product_filter is not None
    assert "productType eq 'women''s bag'" in product_filter
    assert "normalizedBrand eq 'o''neill'" in product_filter
    assert "searchText" not in product_filter


def test_intent_filter_supports_negative_constraints() -> None:
    product_filter = intent_filter(
        QueryIntent(
            searchText="striped sandals that are not black",
            excludedPrimaryColors=["black"],
            excludedAudiences=["men"],
            excludedNormalizedBrands=["o'neill"],
        )
    )

    assert product_filter is not None
    assert "not primaryColors/any(item: item eq 'black')" in product_filter
    assert "not audiences/any(item: item eq 'men')" in product_filter
    assert "normalizedBrand ne 'o''neill'" in product_filter


def test_intent_filter_omits_uncorrelated_types_for_multiple_product_families() -> None:
    product_filter = intent_filter(
        QueryIntent(
            searchText="black purse and sandals",
            productFamilies=["bag", "footwear"],
            productTypes=["purse", "sandals"],
            primaryColors=["black"],
        )
    )

    assert product_filter is not None
    assert "productFamily eq 'bag' or productFamily eq 'footwear'" in product_filter
    assert "primaryColors/any(item: item eq 'black')" in product_filter
    assert "productType" not in product_filter


def test_combined_search_filters_only_explicit_text_constraints() -> None:
    class SearchClientStub:
        def __init__(self) -> None:
            self.options = {}

        def search(self, **options):
            self.options = options
            return []

    client = SearchClientStub()
    services = object.__new__(AzureServices)
    services.search = client
    services.vectorize_image = lambda _image: [0.1] * 1024
    services.understand_image_query = lambda _image, query: QueryIntent(
        searchText="sandals not black",
        productFamilies=["footwear"],
        excludedPrimaryColors=["black"],
    )

    services.search_products(
        SearchRequest(
            query="only if not black",
            mode=SearchMode.COMBINED,
            imageDataUrl="data:image/png;base64,aW1hZ2U=",
        )
    )

    assert client.options["filter"] == (
        "(productFamily eq 'footwear') and "
        "not primaryColors/any(item: item eq 'black')"
    )
    assert client.options["search_text"] == "sandals not black"


def test_combined_search_filters_image_family_and_explicit_audience() -> None:
    class SearchClientStub:
        def __init__(self) -> None:
            self.options = {}

        def search(self, **options):
            self.options = options
            return []

    client = SearchClientStub()
    services = object.__new__(AzureServices)
    services.search = client
    services.vectorize_image = lambda _image: [0.1] * 1024
    services.understand_image_query = lambda _image, query: QueryIntent(
        searchText="black men's sandals",
        productFamilies=["footwear"],
        audiences=["men"],
    )

    services.search_products(
        SearchRequest(
            query="only mens",
            mode=SearchMode.COMBINED,
            imageDataUrl="data:image/png;base64,aW1hZ2U=",
        )
    )

    assert client.options["search_text"] == "black men's sandals"
    assert client.options["filter"] == (
        "(productFamily eq 'footwear') and (audiences/any(item: item eq 'men'))"
    )


def test_v2_adapter_omits_v3_only_constraints() -> None:
    product_filter = intent_filter(
        QueryIntent(
            searchText="white men's slip-on sandals",
            productFamilies=["footwear"],
            productTypes=["sandals"],
            audiences=["men"],
            primaryColors=["white"],
            closureTypes=["slip-on"],
        ),
        {"productTypes", "primaryColors", "materials", "attributes"},
    )

    assert product_filter is not None
    assert "productType eq 'sandals'" in product_filter
    assert "primaryColors/any(item: item eq 'white')" in product_filter
    assert "productFamily" not in product_filter
    assert "audiences" not in product_filter
    assert "closureTypes" not in product_filter


@pytest.mark.parametrize("generic_type", ["slip ons", "slip-on shoes", "athletic shoes"])
def test_v3_filter_keeps_descriptive_facets_for_ranking_only(generic_type: str) -> None:
    product_filter = intent_filter(
        QueryIntent(
            searchText="white slip on shoes for men",
            productFamilies=["footwear"],
            productTypes=[generic_type],
            audiences=["men"],
            primaryColors=["white"],
            styles=["casual"],
            closureTypes=["slip on"],
            attributes=["comfortable"],
        )
    )

    assert product_filter is not None
    assert "productType" not in product_filter
    assert "closureTypes" not in product_filter
    assert "styles" not in product_filter
    assert "attributes" not in product_filter


def test_query_intent_normalizes_and_deduplicates_values() -> None:
    intent = QueryIntent(
        searchText="white sandals",
        productTypes=[" Sandals ", "sandals"],
        primaryColors=[" WHITE"],
    )

    assert intent.productTypes == ["sandals"]
    assert intent.primaryColors == ["white"]


def test_query_intent_uses_canonical_filter_taxonomy() -> None:
    intent = QueryIntent(
        searchText="black handbag and sandal",
        productFamilies=["Handbags"],
        productTypes=["Sandal"],
        audiences=["Male"],
    )

    assert intent.productFamilies == ["bag"]
    assert intent.productTypes == ["sandals"]
    assert intent.audiences == ["men"]


def test_query_intent_rejects_product_type_as_product_family() -> None:
    with pytest.raises(ValueError, match="canonical search taxonomy"):
        QueryIntent(searchText="men's sandals", productFamilies=["sandals"])

    family_items = services_module.QUERY_INTENT_SCHEMA["schema"]["properties"][
        "productFamilies"
    ]["items"]
    assert "footwear" in family_items["enum"]
    assert "sandals" not in family_items["enum"]


def test_query_intent_expands_broad_color_ontology() -> None:
    intent = QueryIntent(searchText="dark crossbody bag", primaryColors=["Dark"])

    assert intent.primaryColors == ["black", "navy", "brown", "gray"]


def test_unconstrained_intent_does_not_add_filter() -> None:
    assert intent_filter(QueryIntent(searchText="something elegant for an evening out")) is None


def test_query_understanding_retries_and_uses_strict_schema() -> None:
    class CompletionsStub:
        def __init__(self) -> None:
            self.attempts = 0
            self.options = {}

        def create(self, **options):
            self.attempts += 1
            self.options = options
            if self.attempts == 1:
                raise RuntimeError("transient")
            content = {
                "searchText": "white men's slip-on sandals",
                "productFamilies": ["footwear"],
                "productTypes": ["sandals"],
                "audiences": ["men"],
                "primaryColors": ["white"],
                "materials": [],
                "styles": [],
                "closureTypes": ["slip-on"],
                "patterns": [],
                "occasions": [],
                "normalizedBrands": [],
                "attributes": [],
            }
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(content)))]
            )

    completions = CompletionsStub()
    services = object.__new__(AzureServices)
    services.settings = SimpleNamespace(azure_openai_vision_deployment="gpt")
    services.vision = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    intent = services.understand_query("WHT slip ons for him")

    assert completions.attempts == 2
    assert completions.options["response_format"]["json_schema"]["strict"] is True
    assert completions.options["messages"][1]["content"] == "WHT slip ons for him"
    assert intent.productTypes == ["sandals"]
    assert intent.audiences == ["men"]


def test_search_falls_back_from_v3_to_v2_to_baseline_adapter(monkeypatch) -> None:
    class FilterRejected(Exception):
        status_code = 400

    class SearchClientStub:
        def __init__(self) -> None:
            self.filters = []

        def search(self, **options):
            self.filters.append(options.get("filter"))
            attempt = len(self.filters)

            def rows():
                if attempt < 3:
                    raise FilterRejected
                yield from ()

            return rows()

    monkeypatch.setattr(services_module, "HttpResponseError", FilterRejected)
    client = SearchClientStub()
    services = object.__new__(AzureServices)
    services.search = client
    services.understand_query = lambda _query: QueryIntent(
        searchText="white sandals",
        productFamilies=["footwear"],
        productTypes=["sandals"],
        primaryColors=["white"],
    )

    services.search_products(SearchRequest(query="white sandals", mode=SearchMode.KEYWORD))

    assert "productFamily" in client.filters[0]
    assert "productType" in client.filters[1]
    assert "productFamily" not in client.filters[1]
    assert client.filters[2] is None


def test_product_enrichment_retries_transient_model_failure() -> None:
    source = BytesIO()
    Image.new("RGB", (1, 1), "white").save(source, format="JPEG")

    class BlobClientStub:
        def download_blob(self, **_options):
            return SimpleNamespace(
                readall=source.getvalue,
                properties=SimpleNamespace(
                    content_settings=SimpleNamespace(content_type="image/jpeg")
                ),
            )

    class CompletionsStub:
        def __init__(self) -> None:
            self.attempts = 0

        def create(self, **_options):
            self.attempts += 1
            if self.attempts < 3:
                raise RuntimeError("transient")
            content = (
                '{"description":"White sandal","productFamily":"footwear",'
                '"productType":"sandals","audiences":[],"primaryColors":["white"],'
                '"materials":[],"styles":[],"closureTypes":[],"patterns":[],'
                '"occasions":[],"normalizedBrand":"","attributes":[],'
                '"searchText":"white sandals footwear","enrichmentConfidence":0.92}'
            )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            )

    completions = CompletionsStub()
    services = object.__new__(AzureServices)
    services.settings = SimpleNamespace(
        azure_blob_container_name="product-images",
        azure_openai_vision_deployment="vision",
    )
    services.blobs = SimpleNamespace(get_blob_client=lambda *_args: BlobClientStub())
    services.vision = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    services.vectorize_image = lambda _content: [0.1] * 1024

    output = services.enrich_product("product.jpg", "Sandal", "Footwear")

    assert completions.attempts == 3
    assert output.productFamily == "footwear"
    assert output.productType == "sandals"
    assert output.enrichmentConfidence == 0.92
    assert output.imageVector is not None
    assert len(output.imageVector) == 1024


def test_metadata_only_enrichment_does_not_download_a_blob() -> None:
    class CompletionsStub:
        def __init__(self) -> None:
            self.options = {}

        def create(self, **options):
            self.options = options
            content = (
                '{"description":"White men’s slip-on sandals",'
                '"productFamily":"footwear","productType":"sandals",'
                '"audiences":["men"],"primaryColors":["white"],"materials":[],'
                '"styles":["casual"],"closureTypes":["slip-on"],"patterns":[],'
                '"occasions":[],"normalizedBrand":"","attributes":[],'
                '"searchText":"white men slip-on sandals chappals footwear",'
                '"enrichmentConfidence":0.9}'
            )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            )

    completions = CompletionsStub()
    services = object.__new__(AzureServices)
    services.settings = SimpleNamespace(
        azure_blob_container_name="product-images",
        azure_openai_vision_deployment="vision",
    )
    services.blobs = SimpleNamespace(
        get_blob_client=lambda *_args: pytest.fail("metadata-only record read Blob storage")
    )
    services.vision = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    output = services.enrich_product("", "WHT M SNDL SLIPON", "FTWR")

    model_content = completions.options["messages"][0]["content"]
    assert len(model_content) == 1
    assert model_content[0]["type"] == "text"
    prompt = model_content[0]["text"]
    assert "WHT M SNDL SLIPON" in prompt
    assert "retailer-specific codebook" in prompt
    assert "M means men" not in prompt
    assert "WHT means white" not in prompt
    assert output.primaryColors == ["white"]
    assert output.audiences == ["men"]

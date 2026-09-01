# Implementation Status

## Completed

1. Provisioned an isolated greenfield resource group and all resources with Bicep and azd.
2. Configured Entra-only access, managed identities, least-privilege RBAC, private Blob and
	Cosmos endpoints, and a Search shared private link to Cosmos.
3. Prepared and uploaded 23 approved product images and loaded 31 synthetic source records,
	including eight metadata-only retail-code fixtures, into Cosmos DB.
4. Deployed the React SPA and FastAPI API together as a non-root Container App.
5. Configured single-tenant MSAL PKCE and protected API and image routes.
6. Created the V1 baseline, V2 enrichment, and V3 normalized indexes, their skillsets and
	indexers, and the stable `tjx-bvx-products-active` alias.
7. Added index-time image enrichment using an authenticated custom Web API skill and
	GPT-5.4-mini structured output.
8. Embedded generated `searchText` with `text-embedding-3-small` and indexed all derived fields
	without changing Cosmos.
9. Replaced phrase rules with strict LLM query intent, canonical taxonomy normalization, escaped
	field-whitelisted filters, and V3/V2/V1 compatibility adapters.
10. Added keyword, vector, hybrid, semantic hybrid, image, and combined text-image search. Image
	queries use bounded vision-to-intent conversion before V3 semantic hybrid retrieval.
11. Added repeatable V1/V2/V3 evaluation and alias switching commands.
12. Activated normalized V3 through `tjx-bvx-products-active` after all release gates passed.

## Validation Completed

- Bicep compilation, subscription validation, and deployment preview.
- Entra and managed-identity authorization paths.
- Search indexer completion: 31 of 31 documents, zero failures, errors, and warnings.
- V1/V2/V3 comparison, V3 semantic execution, and normalized metadata inspection.
- Live relevance checks for `black purse`, `white dress`, and `footwear for beach`.
- Current automated suite: 43 tests passing, Ruff clean, and frontend production build passing.
- Deployed revision healthy; `/healthz` returns `ok` and `/readyz` returns `ready`.

## Search Operations

```powershell
$env:AZURE_SEARCH_ENDPOINT = "https://search-tjx-43ge4ezx44sci.search.windows.net"
.venv\Scripts\python.exe scripts\evaluate_search_variants.py `
  "WHT slip ons for him" "something dark I can wear across my body"
.venv\Scripts\python.exe scripts\switch_search_variant.py status
.venv\Scripts\python.exe scripts\switch_search_variant.py normalized
```

The evaluation command runs identical hybrid queries against V1, V2, and V3 and also executes V3
semantic hybrid ranking. Alias switching supports `baseline`, `enriched`, and `normalized`.

The active alias targets `tjx-bvx-products-enriched-v3`. Representative structured semantic
queries and an image query were validated directly against V3 before activation. A final delegated
HTTP call from Azure CLI requires interactive reauthentication because the local refresh token has
expired; normal SPA sign-in remains the supported user path.

## Deployment Workflow

```powershell
Set-Location C:\temp\Ketaanh\tjx-retail-search-poc
.venv\Scripts\python.exe -m pip install -e ".[dev]"
azd provision --no-prompt
azd deploy web --no-prompt
```

The `prepackage` hook runs Phase 3 validation. The `postdeploy` hook configures the Entra app,
synchronizes the ingestion job image, verifies the custom-skill route, and applies Search
objects. Conditional Access can invalidate the Graph token with
`TokenCreatedWithOutdatedPolicies`; the Container App deployment may still have succeeded.
Reauthenticate before rerunning the hook or its Entra configuration step.

## Remaining Production Work

- Build a human-reviewed relevance set with representative buyer queries.
- Add repeatable relevance metrics and regression thresholds.
- Exercise concurrency, indexer recovery, model throttling, and scale behavior.
- Define operational alerts, retention, support ownership, and cost budgets.
- Complete customer security, privacy, Responsible AI, and data-governance review.

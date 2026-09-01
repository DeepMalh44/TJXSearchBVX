# TJX Product Lens Demo Runbook

## Demo Goal

Show how the same private catalog supports source-code enrichment, natural-language semantic
retrieval, image search, and combined text-image constraints without changing the Cosmos DB source
schema. The active alias targets normalized V3.

Application:
https://ca-tjx-search-43ge4ezx44sci.happymeadow-74ddc1bb.centralus.azurecontainerapps.io/

## Before The Call

1. Open the application and sign in before screen sharing.
2. Keep `C:\temp\Ketaanh\TJX\s7.jpg` ready in File Explorer. It is the supported JPEG demo image
   of blue-and-white striped flip-flops.
3. Open a PowerShell terminal in `C:\temp\Ketaanh\tjx-retail-search-poc` for the optional V1/V2/V3
   comparison.
4. Warm the scale-to-zero application by opening `/healthz`; expect `{"status":"ok"}`.
5. Keep the browser at 100% zoom. Clear the text box when changing scenarios.

The first model-backed request can take longer after idle scale-down. Do not interpret that cold
start as relevance latency.

## Ten-Minute Presenter Script

### 1. Security And Architecture (45 seconds)

**Action:** Show the signed-in application and the six mode buttons.

**Say:**

> This is a private catalog. Microsoft Entra protects the UI and API, managed identities access
> Search, Blob, Cosmos, and Azure OpenAI, and no storage keys or SAS URLs reach the browser. Cosmos
> remains the six-field source of truth. Generated descriptions, taxonomy, and vectors live only in
> Azure AI Search.

**Optional failure proof:** Sign out or use an InPrivate window. Search and image selection are
disabled until sign-in.

### 2. Enrichment Of Dirty Metadata (2 minutes)

**Mode:** `keyword`

**Search:** `WHT M SNDL SLIPON`

**Expected:** `WHT M SNDL SLIPON`, described as a white men's slip-on sandal. The card intentionally
uses the image fallback because this is a metadata-only source record.

**Say:**

> The source contains retail abbreviations, no useful prose, and no image. Index-time GPT enrichment
> expands WHT, M, SNDL, and SLIPON; normalizes family, type, audience, and color; creates natural
> search text; and embeds that text. Nothing generated is written back to Cosmos.

Now switch to `semantic` and search:

`white slip ons for him`

**Expected:** The same `WHT M SNDL SLIPON` record.

**Point to:** The normalized description and the missing-image fallback. This proves that an ugly
source record became discoverable through natural buyer language without inventing a source image.

**Backup enrichment searches:**

| Search | Expected first or only metadata record |
| --- | --- |
| `navy athletic shoe for men` | `NVY M SNEAKR` |
| `white dress for women` | `WHT DRS WMN` |
| `red sandals for women` | `RD WMN SNDL` |
| `black crossbody bag` | `BLK XBODY BAG` |

### 3. Semantic Meaning Versus Literal Words (2 minutes)

**Mode:** `semantic`

**Search:** `something dark I can wear across my body`

**Expected:** `BLK XBODY BAG` is first. Other dark bags can follow.

**Say:**

> The query never says black, handbag, or crossbody. GPT produces strict query intent, canonicalizes
> dark into accepted catalog colors, and preserves crossbody as a product constraint. Azure AI
> Search then runs hybrid retrieval with semantic reranking. Filters run before vector candidate
> selection, so contradictory categories do not leak into the result set.

Follow with a more descriptive query:

`an elegant ivory heel with a jeweled toe`

**Expected:** `S6`, the ivory satin high-heel dress pump.

**What semantic does not mean:** It is not a chat answer and it does not generate products. It
reranks only products already present in the index.

### 4. Image Search (90 seconds)

**Mode:** `image`

1. Choose `C:\temp\Ketaanh\TJX\s7.jpg`.
2. Select **Search**.

**Expected:** `S7`, described as blue-and-white striped flip-flop sandals, should be first.

**Say:**

> GPT vision converts the uploaded image into the same strict product intent used by text search.
> Search then performs semantic hybrid retrieval over the enriched catalog. The browser sends a
> bounded request; the selected image is not written into Cosmos or Blob storage.

**Be precise:** This POC does not use a CLIP-style image vector. It uses image-to-structured-intent,
then searches the catalog's text embeddings and normalized fields.

### 5. Combined Text And Image Search (90 seconds)

**Mode:** `combined`

1. Keep or reselect `s7.jpg`.
2. Enter `blue striped sandals for women`.
3. Select **Search**.

**Expected:** `S7` remains first.

**Say:**

> The image supplies visual evidence such as flip-flop shape and stripes. Text adds explicit buyer
> constraints such as color, product type, and audience. Both inputs become one validated intent
> before retrieval; the model never emits executable OData.

For a shorter combined example, use `casual beach footwear` with the same image.

### 6. Show Safe Failure, Not Just Success (1 minute)

**Mode:** `semantic`

**Search:** `purple winter coat for men`

**Expected:** No matching products.

**Say:**

> Zero is the correct answer. The catalog has no men's purple winter coat, and explicit constraints
> are not relaxed merely to fill the screen. This is preferable to a visually similar but wrong
> product.

Then show an input guardrail:

- In `image` mode, try `d1.avif`. The UI accepts only JPEG, PNG, or WebP and reports the bounded-image
  error. `s7.jpg` is the working demo asset.
- Files over 4 MiB are also rejected client-side and by the API contract.

### 7. Close (30 seconds)

**Say:**

> The POC demonstrates three separable capabilities: enrichment makes sparse catalog data useful;
> semantic hybrid search understands buyer language while enforcing normalized constraints; and
> vision lets an image become a search query. The source schema and partition key remain unchanged,
> V1 and V2 remain available for comparison, and the active alias can roll back without rebuilding
> the application.

## Optional Technical A/B Proof

Run this before the meeting if Azure CLI authentication is current:

```powershell
Set-Location C:\temp\Ketaanh\tjx-retail-search-poc
$env:AZURE_SEARCH_ENDPOINT = "https://search-tjx-43ge4ezx44sci.search.windows.net"
.venv\Scripts\python.exe scripts\evaluate_search_variants.py --top 5 `
  "WHT slip ons for him" `
  "something dark I can wear across my body" `
  "white dress for women" `
  "navy athletic shoe for men"
```

For a concise live explanation, focus on these observed results:

| Query | Useful comparison |
| --- | --- |
| `WHT slip ons for him` | V2 can prefer the tan loafer; V3 and V3 semantic put the white metadata sandal first. |
| `something dark I can wear across my body` | Plain hybrid can rank apparel first; V3 semantic puts the black crossbody record first. |
| `white dress for women` | V3 semantic puts the exact metadata-only white dress first. |
| `navy athletic shoe for men` | The navy metadata sneaker is first across the enriched variants. |

This script queries physical indexes directly. The UI additionally applies validated query intent
and structured constraints, so it is a product behavior demo rather than a raw benchmark UI.

Check the active alias with:

```powershell
.venv\Scripts\python.exe scripts\switch_search_variant.py status
```

Expected index: `tjx-bvx-products-enriched-v3`.

## Failure And Limitation Talking Points

| Observation | Correct explanation |
| --- | --- |
| A metadata-only card has no product photo | Expected. The source record has no image; enrichment does not fabricate one. |
| An unrelated query returns zero results | Expected when hard family, type, audience, color, material, or brand constraints cannot be satisfied. |
| Semantic results differ from keyword results | Semantic is a second-stage reranker over scored candidates; keyword uses lexical BM25 behavior. |
| Relevance score ranges differ by mode | Do not compare raw BM25, RRF, and semantic reranker scores as if they share one scale. |
| First search is slower | Container Apps can scale to zero, and model-backed query understanding adds latency. |
| AVIF upload fails | Intentional POC input boundary. Upload supports JPEG, PNG, and WebP up to 4 MiB. |
| Image search finds a visually related catalog item | Vision creates structured text intent; this is not direct image-vector similarity. |
| The model infers a soft style such as casual | Styles and other descriptive facets influence ranking but do not independently exclude products. |

## Two-Minute Backup Demo

If time is cut short:

1. `semantic` → `white slip ons for him` → show the enriched metadata-only record.
2. `semantic` → `something dark I can wear across my body` → show the black crossbody result.
3. `image` → upload `s7.jpg` → show `S7`.
4. `semantic` → `purple winter coat for men` → show the correct zero-result behavior.

That sequence demonstrates enrichment, semantic meaning, image retrieval, and constraint safety in
roughly two minutes.
# TJX Retail Search Production Cost Estimate

**Estimate date:** September 3, 2026

**Currency:** USD, public pay-as-you-go rates before enterprise discounts, taxes, and support

**Primary region:** Central US

**Catalog size:** 15 million items

## Executive Summary

| Estimate | Cost |
| --- | ---: |
| Single-primary-region recurring production baseline | **$36,411.76/month** |
| Planning budget with 20% contingency | **$43,694.11/month** |
| Annual baseline | **$436,941.12/year** |
| Annual budget with 20% contingency | **$524,329.34/year** |
| Initial 15-million-item enrichment and index build | **$26,358.00 one-time** |
| Initial build budget with 20% contingency | **$31,629.60 one-time** |
| First deployment month, replacing the rebuild reserve with the initial build | **$60,573.26** |

The largest recurring cost is GPT-5.4 mini query understanding because the current application calls it once per search. Azure AI Search is the second-largest fixed cost. Query routing and caching should be validated before production because bypassing GPT for deterministic keyword/filter requests can materially reduce the run rate.

## Production Assumptions

- 15 million active product records in Cosmos DB and Azure AI Search.
- 80% of products, or 12 million items, have an image.
- Average source product record is 4 KB before Cosmos DB indexing overhead.
- Average optimized product image is 250 KB; thumbnails are generated for result pages.
- 10 million searches per month, averaging about 3.9 searches/second and allowing for materially higher peaks during retail events.
- One GPT-5.4 mini query-understanding call per search, using a blended average of 1,200 input and 150 output tokens across text and multimodal requests. The 20% contingency covers moderate image-token and retry variance until measured profiles are available.
- 80% of searches create a text query embedding; each query averages 30 embedded tokens.
- 10% of searches use image or combined mode, producing 1 million Vision query embeddings.
- 30% of searches use semantic reranking, producing 3 million semantic requests.
- Monthly catalog churn is 5%, or 750,000 new/changed products requiring enrichment and reindexing.
- Ongoing product enrichment uses the same blended 1,200-input/150-output GPT token profile. Text-only, metadata-only, and image-bearing products must be measured separately before commitment.
- A new Azure AI Search Standard S2 service uses 3 partitions and 3 replicas, or 9 Search Units. Three replicas provide the query-and-indexing SLA; three partitions provide 1.5 TB storage and 450 GB vector-index quota in Central US for a new service.
- Raw vectors are approximately 141 GB for one index: 15 million 1,536-dimensional text vectors plus 12 million 1,024-dimensional image vectors at four bytes per dimension, before HNSW overhead. Production retains only active and candidate indexes; V1-V3 are deleted. Blue/green indexes approximately double that vector footprint.
- Cosmos DB uses autoscale provisioned throughput across two regions, 50,000 maximum RU/s, with an assumed average hourly peak billing level of 15,000 RU/s per region. At the stated maximum, the throughput range is approximately $876-$8,760/month.
- Container Apps is zone redundant with at least three 1-vCPU/2-GiB serving replicas available and autoscaling to 30. The estimate assumes 20 million active replica-seconds, equivalent to 7.6 continuously active replicas on average; free grants are not deducted.
- 200 GB/month of Application Insights and Log Analytics ingestion with 30-day retention.
- About 3 TB of Hot Blob image storage and a $1,000 monthly allowance for Front Door Premium/WAF, generated-thumbnail delivery, transactions, origin transfer, and outbound image traffic. The delivery design requires edge-compatible authorization and cannot use the POC's private FastAPI proxy unchanged.
- One full 15-million-item rebuild per year is amortized into the recurring baseline to cover schema/model upgrades, recovery, and blue/green replacement.
- 730 hours per month for continuously provisioned resources.

## Recurring Monthly Estimate

| Component | What it is used for in production | Production configuration or usage assumption | Public rate or calculation | Monthly cost |
| --- | --- | --- | ---: | ---: |
| Azure AI Search | Stores 15 million enriched documents and serves keyword, vector, hybrid, semantic, image, and combined retrieval. | Standard S2, 3 partitions x 3 replicas = 9 Search Units | $1.344/SU-hour x 9 x 730 | **$8,830.08** |
| Azure Container Registry | Stores versioned production application and worker images. | Standard tier | $0.6666/day x 30 | **$20.00** |
| Private connectivity | Privately connects Search, Container Apps, Cosmos DB, Blob, Foundry/OpenAI, Vision, and registry paths. | Private endpoints, Search shared private links, and Container Apps environment allowance | Hourly endpoint rates and planning allowance | **$116.80** |
| Private DNS | Resolves private service endpoints within the production virtual network. | Approximately 6 private DNS zones | About $0.50/zone-month | **$3.00** |
| Azure Container Apps serving | Hosts the authenticated React/FastAPI application with redundant, autoscaling replicas. | 20M active replica-seconds at 1 vCPU/2 GiB plus 10M requests | $0.000024/vCPU-s; $0.000003/GiB-s; $0.40/M requests after grants | **$603.20** |
| Catalog enrichment workers | Processes ongoing catalog changes outside the latency-sensitive serving application. | 750,000 changed products/month; queue-based worker allowance | Planning allowance pending load test | **$200.00** |
| GPT-5.4 mini query understanding | Converts shopper text and combined requests into validated intent and filters. | 10M calls; 12B input and 1.5B output tokens | $0.75/M input; $4.50/M output | **$15,750.00** |
| GPT-5.4 mini ongoing enrichment | Produces normalized taxonomy, attributes, confidence, and search text for changed products. | 750,000 products; 900M input and 112.5M output tokens | Same GPT token rates | **$1,181.25** |
| Annual full-catalog rebuild reserve | Funds one repeat of the initial enrichment/index build per year for schema changes, model upgrades, or recovery. | $26,358 initial-build estimate / 12 months | Amortized planning reserve | **$2,196.50** |
| Azure OpenAI text embeddings | Creates query vectors and vectors for changed product text. | 240M query tokens plus 75M index tokens | $0.022/M tokens | **$6.93** |
| Azure AI Vision | Creates image vectors for image searches and changed catalog images. | 1M query images plus 600,000 changed product images | $0.10/1,000 images | **$160.00** |
| Cosmos DB autoscale throughput | Stores the authoritative catalog and supports writes, point reads, and Search indexing. | Two regions; average billable 15,000 RU/s per region | $0.012 per 100 RU/s-hour | **$2,628.00** |
| Cosmos DB storage | Stores source product JSON and indexes in both production regions. | 120 GB logical data/indexes x 2 regions | $0.25/GB-month | **$60.00** |
| Blob image storage | Stores approximately 12 million optimized source product images privately. | Approximately 3 TB Hot storage | Rounded storage/transaction allowance | **$70.00** |
| Front Door/CDN and image delivery | Caches and securely delivers thumbnails without routing every image through the API. | 10M searches/month and optimized result thumbnails | Planning allowance; validate with measured result views and cache hit ratio | **$1,000.00** |
| Log Analytics/Application Insights | Captures production traces, metrics, failures, audit context, and performance telemetry. | 200 GB/month with sampling and 30-day retention | $2.76/GB ingestion | **$552.00** |
| Semantic ranker | Reranks the top Search results for semantic and combined requests. | 3M billable semantic queries, less 1,000 free | $1/1,000 requests | **$2,999.00** |
| Key Vault and backup allowance | Holds operational certificates/configuration where needed and covers backup overhead. | Low transaction volume and backup allowance | Planning allowance | **$35.00** |
| Managed identities, RBAC, VNet, and Entra app registration | Provides passwordless service authentication, authorization, network isolation, and user sign-in. | Current security model, expanded to production scopes | No direct base charge | **$0.00** |
| **Single-primary-region recurring production baseline** |  |  |  | **$36,411.76** |
| **Planning budget with 20% contingency** |  |  |  | **$43,694.11** |

## Initial Catalog Build

The initial load is a one-time first-deployment cost. One rebuild per year is included in the steady-state recurring cost as an amortized reserve. In the first deployment month, replace the $2,196.50 reserve with the $26,358 initial build instead of adding both.

| Component | Initial-build assumption | One-time cost |
| --- | --- | ---: |
| GPT-5.4 mini full enrichment | 15M products at 1,200 input and 150 output tokens | **$23,625.00** |
| Text embeddings | 15M products at about 100 embedded tokens | **$33.00** |
| Vision image embeddings | 12M product images | **$1,200.00** |
| Pipeline compute, retries, and storage operations | Parallel workers, checkpointing, failed-item replay, and blue/green index load | **$1,500.00** |
| **Initial build total** |  | **$26,358.00** |
| **Initial build budget with 20% contingency** |  | **$31,629.60** |

## Capacity Checks

- **Search storage:** S2 provides 512 GB per partition in Central US for a new service. Three partitions provide 1.5 TB total storage.
- **Vector quota:** S2 provides 150 GB of vector-index quota per partition. Three partitions provide 450 GB. The estimated raw vector footprint is 141 GB for one index and 283 GB for blue/green indexes before HNSW overhead.
- **Index lifecycle:** Production keeps only the active and candidate indexes. Retaining POC V1-V3 would consume approximately another 135 GB of raw vector capacity before HNSW overhead and is not supported by this sizing assumption.
- **Availability:** Azure AI Search requires at least two replicas for a query SLA and three replicas for query-and-indexing SLA coverage. The baseline uses three replicas.
- **Document count:** S2 supports up to 24 billion documents per index, so 15 million documents are well below the count limit.
- **Indexer duration:** Large indexer runs can resume on a frequent schedule, but the initial build should use checkpointed batches and controlled parallelism. The current single-worker POC ingestion job is not a production loader.

## Required Validation Before Commitment

1. Load at least 1 million representative products into S2 using the production schema, then use Search service/index statistics to project full and blue/green index storage and vector quota.
2. Run peak-load tests for keyword, vector, hybrid, semantic, image, and combined traffic. Adjust Search replicas based on p95 latency, throttling, and query complexity.
3. Measure GPT tokens and determine what percentage of simple searches can bypass GPT through deterministic routing or caching.
4. Measure Cosmos RU charges for writes, point reads, change processing, and Search indexing. Replace the assumed 15,000 average billable RU/s.
5. Define edge authentication, thumbnail generation, Front Door Premium/WAF policy, image size, result impressions, CDN cache-hit ratio, and egress. Replace the $1,000 image-delivery allowance.
6. Set telemetry sampling and daily caps, then replace the 200-GB log assumption with observed ingestion.
7. Confirm model quota supports peak query and bulk-enrichment throughput; model capacity is a quota setting, not a fixed monthly charge.
8. Obtain Enterprise Agreement or Microsoft Customer Agreement prices and applicable reservations before budget approval.

## Cost Sensitivity

| Change | Approximate monthly impact |
| --- | ---: |
| Every additional 1 million searches with GPT on every request | **+$1,575 GPT**, plus compute and embedding charges |
| Route only 30% of searches through GPT instead of 100% | **-$11,025** |
| Every additional 1 million semantic requests | **+$1,000** |
| Every additional S2 Search Unit | **+$981.12** |
| Increase S2 from 3 x 3 to 4 partitions x 3 replicas | **+$2,943.36** |
| Every additional 1% monthly catalog churn | **About +$236 GPT**, plus embeddings and worker compute |
| Every additional 100 GB of Analytics Logs | **+$276** |
| Every additional 1,000 average billable Cosmos RU/s in two regions | **+$175.20** |
| Cosmos operates at the configured 50,000 RU/s hourly maximum in both regions | **Throughput rises from $2,628 to $8,760** |

## Important Notes

- This is a planning estimate, not an Azure quote or a performance guarantee. It is a single-primary-region Search/application baseline with two-region Cosmos DB, not full regional active/active disaster recovery.
- Search index size cannot be inferred reliably from source size alone. Tokenization, HNSW graphs, vectors, and filterable/facetable fields materially affect storage and latency.
- The 3-partition S2 design is a starting hypothesis. A representative index build is the cheapest reliable test that can confirm or reject it.
- Blue/green deployment requires temporary capacity for two indexes. If HNSW overhead pushes vector usage above quota, use scalar quantization, reduce vector dimensions, avoid storing unnecessary vectors, add a partition, or move to S3.
- Multi-region active/active application hosting, a secondary Azure AI Search service for regional disaster recovery, DDoS Network Protection, Microsoft Defender plans, Azure support plans, taxes, and staff/operational labor are not included.
- A secondary regional Search service would approximately double the Search line and add cross-region replication, hosting, and networking costs.
- Production image delivery should use generated thumbnails and CDN caching. Proxying every original Blob image through FastAPI is not a production-scale delivery design.

## Pricing References

- [Azure AI Search pricing](https://azure.microsoft.com/pricing/details/search/)
- [Azure AI Search service limits](https://learn.microsoft.com/azure/search/search-limits-quotas-capacity)
- [Azure AI Search capacity planning](https://learn.microsoft.com/azure/search/search-capacity-planning)
- [Azure OpenAI pricing](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/)
- [Azure AI Vision pricing](https://azure.microsoft.com/pricing/details/cognitive-services/computer-vision/)
- [Azure Container Apps pricing](https://azure.microsoft.com/pricing/details/container-apps/)
- [Azure Cosmos DB pricing](https://azure.microsoft.com/pricing/details/cosmos-db/autoscale-provisioned/)
- [Azure Blob Storage pricing](https://azure.microsoft.com/pricing/details/storage/blobs/)
- [Azure Front Door pricing](https://azure.microsoft.com/pricing/details/frontdoor/)
- [Azure Private Link pricing](https://azure.microsoft.com/pricing/details/private-link/)
- [Azure Monitor pricing](https://azure.microsoft.com/pricing/details/monitor/)

Recalculate after representative sizing and load tests and before production funding approval.

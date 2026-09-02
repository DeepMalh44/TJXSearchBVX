# TJX Retail Search POC Monthly Cost Estimate

**Estimate date:** September 1, 2026

**Currency:** USD, public pay-as-you-go rates

**Primary region:** Central US

**Vision region:** East US

## Executive Summary

| Estimate | Monthly cost |
| --- | ---: |
| Fixed and low-volume platform estimate | **$120.89** |
| Recommended budget with 10% contingency | **$133.00** |

Azure AI Search Basic and private connectivity make up most of the monthly cost. Azure OpenAI, Vision, Cosmos DB, Storage, and Container Apps are usage-based and inexpensive at POC traffic levels.

## Workload Assumptions

- 10,000 searches per month.
- One GPT-5.4 mini query-understanding call per search.
- Average GPT call: 1,200 input tokens and 150 output tokens.
- 80% of searches use text vectorization: 8,000 embedding operations at about 30 tokens each.
- 10% of searches use image or combined mode: 1,000 query image embeddings.
- Up to 1,000 semantic/combined searches per month under the configured free semantic plan.
- One full enrichment pass over 31 products per month; 23 products have images.
- 1 GB of Log Analytics ingestion per month.
- Less than 1 GB each in Blob Storage and Cosmos DB.
- Container Apps remains configured with `minReplicas: 0`, allowing scale to zero.
- 730 hours per month for continuously allocated resources.
- Free grants are assumed to be available and not consumed by other workloads in the subscription.

## Monthly Estimate

| Component | Deployed SKU/configuration | Public unit price used | POC usage assumption | Estimated monthly cost |
| --- | --- | ---: | ---: | ---: |
| Azure AI Search | Basic, 1 replica x 1 partition = 1 Search Unit; semantic plan `free` | $73.73 per Search Unit/month | 1 Search Unit | **$73.73** |
| Azure Container Registry | Basic; first 10 GB included | $0.167/day | 30 days, under 10 GB | **$5.01** |
| Azure Private Link | 2 explicit private endpoints plus 1 Search shared private link | $0.01/endpoint-hour | 3 x 730 hours | **$21.90** |
| Azure Private DNS | 2 private DNS zones | $0.50/zone/month | 2 zones | **$1.00** |
| Azure Container Apps web/API | Consumption, 0.5 vCPU and 1 GiB, scale to zero | First 180,000 vCPU-s, 360,000 GiB-s, and 2M requests free | 10,000 low-duration requests | **$0.00** |
| Container Apps ingestion job | Consumption, 1 vCPU and 2 GiB | Same consumption grants | One short run/month | **$0.00** |
| Azure OpenAI query understanding | GPT-5.4 mini, Global Standard | $0.75/1M input tokens; $4.50/1M output tokens | 12M input + 1.5M output tokens | **$15.75** |
| Azure OpenAI index enrichment | GPT-5.4 mini, Global Standard | Same token rates | 31 records, one full pass | **$0.10** |
| Azure OpenAI text embeddings | `text-embedding-3-small`, Global Standard | $0.022/1M tokens | About 0.24M query tokens plus index tokens | **$0.01** |
| Azure AI Vision | S1 multimodal image embeddings | $0.10/1,000 image embeddings | 1,000 query + 23 index operations | **$0.10** |
| Azure Cosmos DB | Serverless, single region | About $0.25/1M RU plus $0.25/GB-month | Low indexer/source activity, under 1 GB | **$0.50** |
| Blob Storage | StorageV2 Standard LRS, Hot | Consumption-based storage and operations | Under 1 GB and low transactions | **$0.03** |
| Log Analytics/Application Insights | Pay-as-you-go Analytics Logs, 30-day retention | $2.76/GB ingestion used for estimate | 1 GB | **$2.76** |
| Semantic ranker | Search semantic plan `free` | First 1,000 semantic requests/month free | Up to 1,000 requests | **$0.00** |
| Managed Identity, RBAC, VNet, Entra app registration | No separate SKU charge | No direct charge | Current configuration | **$0.00** |
| **Estimated total** |  |  |  | **$120.89** |
| **Planning budget, rounded with 10% contingency** |  |  |  | **$133.00** |

The executive summary rounds the low-volume estimate to **$121/month**.

## AI Usage Calculation

For 10,000 GPT-5.4 mini calls:

- Input: $10{,}000 \times 1{,}200 = 12{,}000{,}000$ tokens.
- Input cost: $12 \times \$0.75 = \$9.00$.
- Output: $10{,}000 \times 150 = 1{,}500{,}000$ tokens.
- Output cost: $1.5 \times \$4.50 = \$6.75$.
- Total query-understanding cost: **$15.75/month**.

The deployment capacity value of `10` for the Global Standard model is a throughput quota setting, not reserved capacity. It does not create a fixed monthly model charge; token usage is billed.

## Cost Sensitivity

| Change | Approximate impact |
| --- | ---: |
| Every additional 10,000 searches at the same token profile | +$15.75 GPT cost, plus small embedding/compute charges |
| Every additional 1,000 image searches | +$0.10 Vision cost, plus GPT image-token variation |
| Semantic plan changed to Standard | First 1,000 semantic requests free, then about $1 per additional 1,000 requests |
| Keep one Container Apps replica always available | Adds idle/active compute cost; estimate separately from actual uptime |
| Add one Search replica or partition | Adds another Search Unit, approximately +$73.73/month at Basic pricing |
| Each additional private endpoint | Approximately +$7.30/month, plus processed data |
| Each additional 1 GB of Analytics Logs | Approximately +$2.76/month |

## Important Notes

- This is a planning estimate, not an Azure quote or invoice forecast.
- Public retail prices can differ from the organization's Enterprise Agreement, Microsoft Customer Agreement, negotiated discounts, taxes, and currency conversion.
- Image inputs to GPT are tokenized based on image properties. The blended 1,200-input-token assumption should be replaced with measured token usage after representative testing.
- Private Link data processing and internet/cross-region egress are excluded because this POC has very low data volume. The hourly endpoint charges are included.
- The Search shared private link is included conservatively as a third billable Private Link connection.
- The free Container Apps grants are subscription-wide. If another workload consumes them, this POC incurs active vCPU, memory, and request charges.
- The configured Search semantic plan is free and limited. Raising it to Standard changes both capacity and cost behavior.
- Application Insights uses the Log Analytics workspace, so its primary POC charge is represented under log ingestion rather than as a separate base fee.
- Search Basic is continuously billed while the service exists, even when no searches are running.

## Pricing References

- [Azure AI Search pricing](https://azure.microsoft.com/pricing/details/search/)
- [Azure AI Search cost planning](https://learn.microsoft.com/azure/search/search-sku-manage-costs)
- [Azure OpenAI pricing](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/)
- [Azure Vision pricing](https://azure.microsoft.com/pricing/details/cognitive-services/computer-vision/)
- [Azure Container Apps pricing](https://azure.microsoft.com/pricing/details/container-apps/)
- [Azure Container Registry pricing](https://azure.microsoft.com/pricing/details/container-registry/)
- [Azure Cosmos DB pricing](https://azure.microsoft.com/pricing/details/cosmos-db/autoscale-provisioned/)
- [Azure Private Link pricing](https://azure.microsoft.com/pricing/details/private-link/)
- [Azure DNS pricing](https://azure.microsoft.com/pricing/details/dns/)
- [Azure Monitor pricing](https://azure.microsoft.com/pricing/details/monitor/)

Recalculate this estimate before production sizing. Production generally needs additional Search replicas for availability, higher traffic assumptions, monitoring volume, load testing, and an explicit semantic ranker plan.

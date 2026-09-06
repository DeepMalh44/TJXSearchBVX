# TJX AI Search Diagram Set

The editable workbook [`tjx-ai-search-diagrams.drawio`](tjx-ai-search-diagrams.drawio) contains the architecture views required to review the TJX multimodal product-search solution.

## Pages

| Page | Question answered |
| --- | --- |
| 01 Solution Context | Who uses the system, which Azure services participate, and where source and derived data live? |
| 02 Deployment and Network | Which endpoints are public or private, how are subnets and private endpoints arranged, and where does traffic cross trust boundaries? |
| 03 Online Search Flow | How do authenticated search modes execute, and which steps invoke GPT-5.4-mini, `text-embedding-3-small`, Azure AI Vision, Search, and Blob Storage? |
| 04 Ingestion and Indexing | How do GPT taxonomy enrichment, text embedding, and image embedding produce a versioned Search document without modifying source data? |
| 05 Identity and Security | Which human and workload identities access each resource, and through which scoped roles? |
| 06 DevOps Operations Recovery | How is the solution deployed, monitored, scaled, rolled back, and recovered within the proposed one-day RTO? |
| 07 Data Ownership and Schema | Which fields remain authoritative, which are derived for retrieval, and how do text/image vectors and metadata-only products behave? |

## State Model

**Observed:** The deployed POC uses Basic Azure AI Search with one partition and one replica. The Container App has public TLS ingress protected by Microsoft Entra ID. Blob Storage and Cosmos DB use private endpoints; Search reaches Cosmos through a shared private link. Search, Azure OpenAI, Azure AI Vision, and the Container App retain public endpoints with identity-based authorization.

**Assumption:** The first production release starts with 1 million products, 60% with images, S2 Search with one partition and two replicas, US-only TJX employee access, no Azure Front Door, and a one-day RTO.

**Risk:** Product-volume sizing, HNSW overhead, peak request concurrency, AI token use, model quotas, source backup settings, operational alerts, and the one-day recovery sequence have not been proven through production-scale tests.

**Decision needed:** Confirm whether vendors require external access. That decision controls ingress, WAF/edge protection, Conditional Access, identity federation, and whether the no-AFD assumption remains valid.

**Tradeoff:** One partition and two replicas minimize initial Search cost while retaining query availability. Additional partitions should be driven by measured storage, vector quota, and indexing throughput; additional replicas should be driven by query throughput and availability requirements.

## Architecture Review

- **Reliability:** Versioned indexes and a stable alias provide application-level rollback. A secondary Search service and active/active regional path are intentionally excluded. RPO and backup policies remain open.
- **Security:** Entra tokens, managed identities, resource-scoped RBAC, private source stores, safe blob-name validation, and canonical filter allowlists are present. Delegated scope enforcement, vendor identity, private AI endpoints, egress controls, and security operations integration require decisions.
- **Cost optimization:** Search units and GPT query traffic are the principal drivers. Starting with one partition and two replicas is appropriate for the proposed 1-million-item launch, subject to measured index size and load tests.
- **Operational excellence:** Infrastructure and Search objects are repeatable through azd, Bicep, and scripts. Production alert rules, incident ownership, runbooks, and rollback approvals remain to be established.
- **Performance efficiency:** Text and image vectors use separate spaces and Search supports six retrieval modes. Representative indexing, p95 query latency, throttling, and vector-headroom tests are required before final sizing.

## Validation

Validate the editable workbook with:

```powershell
python "$HOME/.copilot/skills/azure-architecture-diagram-generator/scripts/validate-azure-drawio.py" docs/tjx-ai-search-diagrams.drawio --strict
```

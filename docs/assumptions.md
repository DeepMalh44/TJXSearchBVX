# Assumptions And Decisions

| ID | Current decision | Consequence |
| --- | --- | --- |
| A-001 | The POC is isolated in `rg-tjx-retail-search-poc-greenfield`. | It does not discover, reference, or modify the earlier TJX/BVX environment. |
| A-002 | The 23 approved images and records are synthetic POC inputs. | Results demonstrate behavior, not production catalog quality or scale. |
| A-003 | Cosmos DB is the source of truth and its product schema remains unchanged. | AI-generated fields exist only in Search and can be rebuilt by reindexing. |
| A-004 | GPT-5.4-mini performs product-only visual enrichment. | Strict output and prompt constraints exclude backgrounds and unrelated props. |
| A-005 | `text-embedding-3-small` provides index-time and query-time vectorization. | Model deployment and dimensions remain infrastructure parameters. |
| A-006 | Both Search variants remain deployed behind one alias. | A/B switching does not require an application deployment. |
| A-007 | Explicit color and product-family intent constrains candidate products. | Similarity cannot introduce clearly wrong families for recognized intent. |
| A-008 | Private images are served through the authenticated backend. | No storage keys or persistent SAS URLs reach the browser or catalog. |
| A-009 | Generated relevance judgments are not accepted as evidence. | Quality claims require human-reviewed expected results. |
| A-010 | Basic Search and scale-to-zero Container Apps are adequate for this POC. | Production sizing must use measured indexing, model, and query load. |

The enriched index is currently active. Future source redesign is justified only by measured
catalog needs such as unstable identifiers, high update volume, partition hot spots, security
trimming, or relationships the current product record cannot represent.

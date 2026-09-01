# Resource Ownership

This project is a greenfield deployment and does not discover or reuse resources from other
resource groups. All resources are managed inside `rg-tjx-retail-search-poc-greenfield`.

Project-owned resources include the application managed identity, Storage account and private
Blob container, Cosmos account/database/container, Search service and data-plane objects, Azure
OpenAI account and model deployments, ACR, Container Apps environment, web app, manual ingestion
job, networking/private endpoints, Log Analytics, Application Insights, and deterministic role
assignments.

Search objects include baseline V1, enriched V2, their skillsets and indexers, and
`tjx-bvx-products-active`, which currently targets enriched V2. The deployment is incremental
and rerunnable. Cleanup remains limited to the project-owned resource manifest.

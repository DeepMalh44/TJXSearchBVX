// Hosts both serving and one-shot ingestion from the same immutable application image.
// Private endpoints protect source data; Search uses its own shared private link to Cosmos.
param resourceToken string
param location string
param tags object
param applicationIdentityResourceId string
param applicationPrincipalId string
param applicationClientId string
param storageAccountName string
param storageAccountResourceId string
param cosmosAccountName string
param cosmosAccountResourceId string
param openAIAccountName string
param visionEndpoint string
param searchEndpoint string
param searchPrincipalId string
param blobEndpoint string
param cosmosEndpoint string
param entraTenantId string
param entraClientId string
param entraApiAudience string
param imageName string

var names = {
  acr: 'acrtjx${resourceToken}'
  app: 'ca-tjx-search-${resourceToken}'
  environment: 'cae-tjx-search-${resourceToken}'
  insights: 'appi-tjx-search-${resourceToken}'
  job: 'caj-tjx-ingest-${resourceToken}'
  logs: 'log-tjx-search-${resourceToken}'
  vnet: 'vnet-tjx-search-${resourceToken}'
}
var applicationImage = empty(imageName) ? 'mcr.microsoft.com/k8se/quickstart:latest' : imageName
// Every workload call uses the user-assigned identity; no data-plane keys are injected.
var commonEnv = [
  { name: 'AZURE_TENANT_ID', value: entraTenantId }
  { name: 'AZURE_AD_CLIENT_ID', value: entraClientId }
  { name: 'AZURE_APPLICATION_CLIENT_ID', value: applicationClientId }
  { name: 'ENTRA_API_AUDIENCE', value: entraApiAudience }
  { name: 'AZURE_SEARCH_ENDPOINT', value: searchEndpoint }
  { name: 'AZURE_SEARCH_INDEX', value: 'tjx-bvx-products-active' }
  { name: 'AZURE_SEARCH_PRINCIPAL_ID', value: searchPrincipalId }
  { name: 'AZURE_BLOB_ENDPOINT', value: blobEndpoint }
  { name: 'AZURE_BLOB_CONTAINER_NAME', value: 'product-images' }
  { name: 'AZURE_COSMOS_ENDPOINT', value: cosmosEndpoint }
  { name: 'AZURE_COSMOS_DATABASE', value: 'retail-search-poc' }
  { name: 'AZURE_COSMOS_CONTAINER', value: 'products' }
  { name: 'AZURE_OPENAI_ENDPOINT', value: 'https://${openAIAccountName}.openai.azure.com/' }
  { name: 'AZURE_OPENAI_VISION_DEPLOYMENT', value: 'gpt-5.4-mini' }
  { name: 'AZURE_AI_VISION_ENDPOINT', value: visionEndpoint }
]

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: names.acr
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false, anonymousPullEnabled: false, publicNetworkAccess: 'Enabled' }
}
resource logs 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: names.logs
  location: location
  tags: tags
  properties: { retentionInDays: 30 }
  sku: { name: 'PerGB2018' }
}
resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: names.insights
  location: location
  kind: 'web'
  tags: tags
  properties: { Application_Type: 'web', WorkspaceResourceId: logs.id }
}
resource vnet 'Microsoft.Network/virtualNetworks@2024-07-01' = {
  name: names.vnet
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: ['10.42.0.0/16'] }
    subnets: [
      { name: 'container-apps', properties: { addressPrefix: '10.42.0.0/23', delegations: [{ name: 'container-apps', properties: { serviceName: 'Microsoft.App/environments' } }] } }
      { name: 'private-endpoints', properties: { addressPrefix: '10.42.2.0/24', privateEndpointNetworkPolicies: 'Disabled' } }
    ]
  }
}
resource blobDns 'Microsoft.Network/privateDnsZones@2024-06-01' = { name: 'privatelink.blob.core.windows.net', location: 'global', tags: tags }
resource cosmosDns 'Microsoft.Network/privateDnsZones@2024-06-01' = { name: 'privatelink.documents.azure.com', location: 'global', tags: tags }
resource blobDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = { name: 'blob-${resourceToken}', parent: blobDns, location: 'global', properties: { registrationEnabled: false, virtualNetwork: { id: vnet.id } } }
resource cosmosDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = { name: 'cosmos-${resourceToken}', parent: cosmosDns, location: 'global', properties: { registrationEnabled: false, virtualNetwork: { id: vnet.id } } }
resource blobPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-07-01' = {
  name: 'pe-${storageAccountName}-blob'
  location: location
  tags: tags
  properties: { subnet: { id: resourceId('Microsoft.Network/virtualNetworks/subnets', vnet.name, 'private-endpoints') }, privateLinkServiceConnections: [{ name: 'blob', properties: { privateLinkServiceId: storageAccountResourceId, groupIds: ['blob'] } }] }
}
resource blobDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-07-01' = { name: 'default', parent: blobPrivateEndpoint, properties: { privateDnsZoneConfigs: [{ name: 'blob', properties: { privateDnsZoneId: blobDns.id } }] } }
resource cosmosPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-07-01' = {
  name: 'pe-${cosmosAccountName}-sql'
  location: location
  tags: tags
  properties: { subnet: { id: resourceId('Microsoft.Network/virtualNetworks/subnets', vnet.name, 'private-endpoints') }, privateLinkServiceConnections: [{ name: 'cosmos', properties: { privateLinkServiceId: cosmosAccountResourceId, groupIds: ['Sql'] } }] }
}
resource cosmosDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-07-01' = { name: 'default', parent: cosmosPrivateEndpoint, properties: { privateDnsZoneConfigs: [{ name: 'cosmos', properties: { privateDnsZoneId: cosmosDns.id } }] } }
resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: names.environment
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: { destination: 'log-analytics', logAnalyticsConfiguration: { customerId: logs.properties.customerId, sharedKey: logs.listKeys().primarySharedKey } }
    vnetConfiguration: { infrastructureSubnetId: resourceId('Microsoft.Network/virtualNetworks/subnets', vnet.name, 'container-apps'), internal: false }
    workloadProfiles: [{ name: 'Consumption', workloadProfileType: 'Consumption' }]
  }
}
// The public ingress terminates TLS, while every catalog and image route enforces Entra.
resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: names.app
  location: location
  tags: union(tags, { 'azd-service-name': 'web' })
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${applicationIdentityResourceId}': {} } }
  properties: {
    managedEnvironmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: { activeRevisionsMode: 'Single', ingress: { external: true, targetPort: 8000, transport: 'auto', allowInsecure: false }, registries: [{ server: registry.properties.loginServer, identity: applicationIdentityResourceId }] }
    template: {
      containers: [{ name: 'web', image: applicationImage, env: commonEnv, probes: [{ type: 'Liveness', httpGet: { path: '/healthz', port: 8000 }, initialDelaySeconds: 10, periodSeconds: 30 }, { type: 'Readiness', httpGet: { path: '/readyz', port: 8000 }, initialDelaySeconds: 10, periodSeconds: 20 }], resources: { cpu: json('0.5'), memory: '1Gi' } }]
      scale: { minReplicas: 0, maxReplicas: 3, rules: [{ name: 'http', http: { metadata: { concurrentRequests: '50' } } }] }
    }
  }
}
// The manual job seeds Blob and Cosmos, then exits; Search enrichment runs separately.
resource job 'Microsoft.App/jobs@2024-03-01' = {
  name: names.job
  location: location
  tags: tags
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${applicationIdentityResourceId}': {} } }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: { triggerType: 'Manual', replicaTimeout: 3600, replicaRetryLimit: 0, manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }, registries: [{ server: registry.properties.loginServer, identity: applicationIdentityResourceId }] }
    template: { containers: [{ name: 'ingestion', image: applicationImage, command: ['python', '-m', 'app.ingestion.run'], env: commonEnv, resources: { cpu: json('1.0'), memory: '2Gi' } }] }
  }
}
resource openAI 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = { name: openAIAccountName }
resource visionDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  name: 'gpt-5.4-mini'
  parent: openAI
  sku: { name: 'GlobalStandard', capacity: 10 }
  properties: { model: { format: 'OpenAI', name: 'gpt-5.4-mini', version: '2026-03-17' }, versionUpgradeOption: 'OnceNewDefaultVersionAvailable' }
}
var acrPullRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, applicationPrincipalId, acrPullRole)
  scope: registry
  properties: { principalId: applicationPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: acrPullRole }
}
output appName string = app.name
output appUri string = 'https://${app.properties.configuration.ingress.fqdn}'
output registryEndpoint string = registry.properties.loginServer
output registryName string = registry.name
output jobName string = job.name

targetScope = 'subscription'

@description('Name of the azd environment.')
param environmentName string

@description('Azure region for resources created by this deployment.')
param location string

@description('Azure region that supports Vision multimodal embeddings.')
param visionLocation string = 'eastus'

@description('Name of the resource group created for this isolated POC.')
param resourceGroupName string = 'rg-tjx-retail-search-poc-greenfield'

@description('Azure OpenAI embedding model name.')
param embeddingModelName string

@description('Azure OpenAI embedding model version.')
param embeddingModelVersion string

@description('Name exposed for the embedding model deployment.')
param embeddingDeploymentName string = 'text-embedding-3-small'

@minValue(1)
@description('Vector dimensions emitted by the selected embedding model.')
param embeddingDimensions int

@minValue(1)
@description('Token capacity allocated to the embedding model deployment.')
param embeddingCapacity int

@description('Optional object ID granted temporary bootstrap access for Search object and sample-data configuration.')
param deploymentPrincipalId string = ''

param entraTenantId string = tenant().tenantId
param entraClientId string = '00000000-0000-0000-0000-000000000000'
param entraApiAudience string = 'api://${entraClientId}'
@description('Optional ACR image reference. Empty uses a Microsoft public placeholder for initial provisioning.')
param serviceImageName string = ''

var resourceToken = toLower(uniqueString(subscription().id, resourceGroupName, environmentName))
var names = {
  applicationIdentity: 'id-tjx-search-${resourceToken}'
  cosmos: 'cosmos-tjx-${resourceToken}'
  openAI: 'aoai-tjx-${resourceToken}'
  search: 'search-tjx-${resourceToken}'
  storage: 'sttjx${resourceToken}'
  vision: 'cv-tjx-${resourceToken}'
}
var tags = {
  Environment: environmentName
  ManagedBy: 'azd'
  Workload: 'tjx-retail-search-poc'
  'azd-env-name': environmentName
}

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-11-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module applicationIdentity 'modules/identity.bicep' = {
  name: 'create-application-identity'
  scope: resourceGroup
  params: {
    identityName: names.applicationIdentity
    location: location
    tags: tags
  }
}

module searchAuth 'modules/search-auth.bicep' = {
  name: 'create-search'
  scope: resourceGroup
  params: {
    cosmosAccountResourceId: cosmos.outputs.resourceId
    location: location
    searchServiceName: names.search
    tags: tags
  }
}

module cosmos 'modules/cosmos.bicep' = {
  name: 'create-cosmos'
  scope: resourceGroup
  params: {
    cosmosAccountName: names.cosmos
    location: location
    tags: tags
  }
}

module dataServices 'modules/data-services.bicep' = {
  name: 'create-data-services'
  scope: resourceGroup
  params: {
    embeddingCapacity: embeddingCapacity
    embeddingDeploymentName: embeddingDeploymentName
    embeddingModelName: embeddingModelName
    embeddingModelVersion: embeddingModelVersion
    location: location
    openAIAccountName: names.openAI
    storageAccountName: names.storage
    tags: tags
    visionAccountName: names.vision
    visionLocation: visionLocation
  }
}

module access 'modules/access.bicep' = {
  name: 'configure-access'
  scope: resourceGroup
  params: {
    applicationPrincipalId: applicationIdentity.outputs.principalId
    cosmosAccountName: cosmos.outputs.name
    deploymentPrincipalId: deploymentPrincipalId
    openAIAccountName: dataServices.outputs.openAIName
    searchPrincipalId: searchAuth.outputs.systemAssignedPrincipalId
    searchServiceName: searchAuth.outputs.name
    storageAccountName: dataServices.outputs.storageAccountName
    visionAccountName: dataServices.outputs.visionName
  }
}

module phase3 'modules/phase3.bicep' = {
  name: 'create-phase3-hosting'
  scope: resourceGroup
  params: {
    applicationClientId: applicationIdentity.outputs.clientId
    applicationIdentityResourceId: applicationIdentity.outputs.resourceId
    applicationPrincipalId: applicationIdentity.outputs.principalId
    blobEndpoint: dataServices.outputs.blobEndpoint
    cosmosAccountName: cosmos.outputs.name
    cosmosAccountResourceId: cosmos.outputs.resourceId
    cosmosEndpoint: cosmos.outputs.endpoint
    entraApiAudience: entraApiAudience
    entraClientId: entraClientId
    entraTenantId: entraTenantId
    imageName: serviceImageName
    location: location
    openAIAccountName: dataServices.outputs.openAIName
    resourceToken: resourceToken
    searchEndpoint: searchAuth.outputs.endpoint
    searchPrincipalId: searchAuth.outputs.systemAssignedPrincipalId
    storageAccountName: dataServices.outputs.storageAccountName
    storageAccountResourceId: dataServices.outputs.storageAccountResourceId
    tags: tags
    visionEndpoint: dataServices.outputs.visionEndpoint
  }
}

output AZURE_APPLICATION_CLIENT_ID string = applicationIdentity.outputs.clientId
output AZURE_APPLICATION_IDENTITY_NAME string = applicationIdentity.outputs.name
output AZURE_BLOB_CONTAINER_NAME string = dataServices.outputs.blobContainerName
output AZURE_BLOB_ENDPOINT string = dataServices.outputs.blobEndpoint
output AZURE_ENV_NAME string = environmentName
output AZURE_COSMOS_ENDPOINT string = cosmos.outputs.endpoint
output AZURE_COSMOS_NAME string = cosmos.outputs.name
output AZURE_COSMOS_RESOURCE_ID string = cosmos.outputs.resourceId
output AZURE_EMBEDDING_DEPLOYMENT string = embeddingDeploymentName
output AZURE_EMBEDDING_DIMENSIONS int = embeddingDimensions
output AZURE_EMBEDDING_MODEL string = embeddingModelName
output AZURE_LOCATION string = location
output AZURE_OPENAI_ENDPOINT string = dataServices.outputs.openAIEndpoint
output AZURE_OPENAI_NAME string = dataServices.outputs.openAIName
output AZURE_AI_VISION_ENDPOINT string = dataServices.outputs.visionEndpoint
output AZURE_AI_VISION_NAME string = dataServices.outputs.visionName
output AZURE_RESOURCE_GROUP string = resourceGroup.name
output AZURE_SEARCH_ENDPOINT string = searchAuth.outputs.endpoint
output AZURE_SEARCH_PRINCIPAL_ID string = searchAuth.outputs.systemAssignedPrincipalId
output AZURE_SEARCH_SERVICE_NAME string = searchAuth.outputs.name
output AZURE_CONTAINER_APP_NAME string = phase3.outputs.appName
output AZURE_CONTAINER_APP_URI string = phase3.outputs.appUri
output AZURE_CONTAINER_JOB_NAME string = phase3.outputs.jobName
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = phase3.outputs.registryEndpoint
output AZURE_CONTAINER_REGISTRY_MANAGED_IDENTITY_ID string = applicationIdentity.outputs.resourceId
output AZURE_CONTAINER_REGISTRY_NAME string = phase3.outputs.registryName
output MANAGED_IDENTITY_CLIENT_ID string = applicationIdentity.outputs.clientId
output SERVICE_WEB_NAME string = phase3.outputs.appName
output SERVICE_WEB_URI string = phase3.outputs.appUri

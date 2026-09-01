@description('Name of the Storage Account created for the POC.')
param storageAccountName string

@description('Name of the Azure OpenAI account created for the POC.')
param openAIAccountName string

@description('Name of the Azure AI Vision account created for native image embeddings.')
param visionAccountName string

@description('Azure region that supports Vision multimodal embeddings.')
param visionLocation string

@description('Azure region for the data services.')
param location string

@description('Tags assigned to the data services.')
param tags object

@description('Azure OpenAI embedding model name.')
param embeddingModelName string

@description('Azure OpenAI embedding model version.')
param embeddingModelVersion string

@description('Name exposed for the embedding model deployment.')
param embeddingDeploymentName string

@minValue(1)
@description('Token capacity allocated to the embedding model deployment.')
param embeddingCapacity int

resource storageAccount 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: storageAccountName
  location: location
  tags: union(tags, {
    Security: 'Exception'
    SecurityControl: 'Ignore'
  })
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Disabled'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2025-01-01' = {
  name: 'default'
  parent: storageAccount
}

resource productImagesContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01' = {
  name: 'product-images'
  parent: blobService
  properties: {
    publicAccess: 'None'
  }
}

resource openAIAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: openAIAccountName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: openAIAccountName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource visionAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: visionAccountName
  location: visionLocation
  tags: tags
  kind: 'ComputerVision'
  sku: {
    name: 'S1'
  }
  properties: {
    customSubDomainName: visionAccountName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  name: embeddingDeploymentName
  parent: openAIAccount
  sku: {
    name: 'GlobalStandard'
    capacity: embeddingCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModelName
      version: embeddingModelVersion
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

output blobContainerName string = productImagesContainer.name
output blobContainerResourceId string = productImagesContainer.id
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob
output openAIEndpoint string = openAIAccount.properties.endpoint
output openAIName string = openAIAccount.name
output openAIResourceId string = openAIAccount.id
output storageAccountName string = storageAccount.name
output storageAccountResourceId string = storageAccount.id
output visionEndpoint string = visionAccount.properties.endpoint
output visionName string = visionAccount.name

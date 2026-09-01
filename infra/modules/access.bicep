@description('Object ID of the application managed identity created by this deployment.')
param applicationPrincipalId string

@description('Optional object ID used to configure Search objects and bootstrap sample data.')
param deploymentPrincipalId string = ''

@description('Object ID of the Search service system-assigned managed identity.')
param searchPrincipalId string

@description('Name of the Search service created by this deployment.')
param searchServiceName string

@description('Name of the Storage Account created by this deployment.')
param storageAccountName string

@description('Name of the Azure OpenAI account created by this deployment.')
param openAIAccountName string

@description('Name of the Azure AI Vision account created by this deployment.')
param visionAccountName string

@description('Name of the Cosmos DB account created by this deployment.')
param cosmosAccountName string

var roleDefinitionIds = {
  azureAIEnterpriseNetworkConnectionApprover: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b556d68e-0be0-4f35-a333-ad7ee1ce17ea')
  cognitiveServicesOpenAIUser: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  cognitiveServicesUser: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
  cosmosDBAccountReader: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'fbdf93bf-df7d-467e-a4d2-9458aa1360c8')
  searchIndexDataContributor: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
  searchIndexDataReader: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '1407120a-92aa-4202-b7e9-c0e197c71c8f')
  searchServiceContributor: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7ca78c08-252a-4471-8644-bb5ff32d4ba0')
  storageBlobDataContributor: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  storageBlobDataReader: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
}

resource searchService 'Microsoft.Search/searchServices@2025-05-01' existing = {
  name: searchServiceName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2025-01-01' existing = {
  name: storageAccountName

  resource blobService 'blobServices' existing = {
    name: 'default'

    resource productImages 'containers' existing = {
      name: 'product-images'
    }
  }
}

resource openAIAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: openAIAccountName
}

resource visionAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: visionAccountName
}

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = {
  name: cosmosAccountName
}

resource deploymentSearchServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deploymentPrincipalId)) {
  name: guid(searchService.id, deploymentPrincipalId, roleDefinitionIds.searchServiceContributor)
  scope: searchService
  properties: {
    principalId: deploymentPrincipalId
    roleDefinitionId: roleDefinitionIds.searchServiceContributor
  }
}

resource deploymentSearchIndexContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deploymentPrincipalId)) {
  name: guid(searchService.id, deploymentPrincipalId, roleDefinitionIds.searchIndexDataContributor)
  scope: searchService
  properties: {
    principalId: deploymentPrincipalId
    roleDefinitionId: roleDefinitionIds.searchIndexDataContributor
  }
}

resource deploymentBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deploymentPrincipalId)) {
  name: guid(storageAccount::blobService::productImages.id, deploymentPrincipalId, roleDefinitionIds.storageBlobDataContributor)
  scope: storageAccount::blobService::productImages
  properties: {
    principalId: deploymentPrincipalId
    roleDefinitionId: roleDefinitionIds.storageBlobDataContributor
  }
}

resource deploymentOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deploymentPrincipalId)) {
  name: guid(openAIAccount.id, deploymentPrincipalId, roleDefinitionIds.cognitiveServicesOpenAIUser)
  scope: openAIAccount
  properties: {
    principalId: deploymentPrincipalId
    roleDefinitionId: roleDefinitionIds.cognitiveServicesOpenAIUser
  }
}

resource deploymentCosmosContributor 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = if (!empty(deploymentPrincipalId)) {
  name: guid(cosmosAccount.id, deploymentPrincipalId, 'cosmos-data-contributor')
  parent: cosmosAccount
  properties: {
    principalId: deploymentPrincipalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    scope: cosmosAccount.id
  }
}

resource deploymentCosmosPrivateEndpointApprover 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deploymentPrincipalId)) {
  name: guid(cosmosAccount.id, deploymentPrincipalId, roleDefinitionIds.azureAIEnterpriseNetworkConnectionApprover)
  scope: cosmosAccount
  properties: {
    principalId: deploymentPrincipalId
    roleDefinitionId: roleDefinitionIds.azureAIEnterpriseNetworkConnectionApprover
  }
}

resource searchCosmosReader 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = {
  name: guid(cosmosAccount.id, searchPrincipalId, 'cosmos-data-reader')
  parent: cosmosAccount
  properties: {
    principalId: searchPrincipalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000001'
    scope: cosmosAccount.id
  }
}

resource searchCosmosAccountReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(cosmosAccount.id, searchPrincipalId, roleDefinitionIds.cosmosDBAccountReader)
  scope: cosmosAccount
  properties: {
    principalId: searchPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionIds.cosmosDBAccountReader
  }
}

resource searchOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAIAccount.id, searchPrincipalId, roleDefinitionIds.cognitiveServicesOpenAIUser)
  scope: openAIAccount
  properties: {
    principalId: searchPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionIds.cognitiveServicesOpenAIUser
  }
}

resource applicationSearchReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, applicationPrincipalId, roleDefinitionIds.searchIndexDataReader)
  scope: searchService
  properties: {
    principalId: applicationPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionIds.searchIndexDataReader
  }
}

resource applicationBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount::blobService::productImages.id, applicationPrincipalId, roleDefinitionIds.storageBlobDataContributor)
  scope: storageAccount::blobService::productImages
  properties: {
    principalId: applicationPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionIds.storageBlobDataContributor
  }
}

resource applicationCosmosContributor 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = {
  name: guid(cosmosAccount.id, applicationPrincipalId, 'cosmos-data-contributor')
  parent: cosmosAccount
  properties: {
    principalId: applicationPrincipalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    scope: cosmosAccount.id
  }
}

resource applicationOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAIAccount.id, applicationPrincipalId, roleDefinitionIds.cognitiveServicesOpenAIUser)
  scope: openAIAccount
  properties: {
    principalId: applicationPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionIds.cognitiveServicesOpenAIUser
  }
}

resource applicationVisionUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(visionAccount.id, applicationPrincipalId, roleDefinitionIds.cognitiveServicesUser)
  scope: visionAccount
  properties: {
    principalId: applicationPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionIds.cognitiveServicesUser
  }
}

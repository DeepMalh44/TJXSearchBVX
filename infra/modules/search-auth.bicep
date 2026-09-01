@description('Name of the Azure AI Search service created for the POC.')
param searchServiceName string

@description('Azure region for the Search service.')
param location string

@description('Tags assigned to the Search service.')
param tags object

@description('Resource ID of the Cosmos DB account reached through Search shared private access.')
param cosmosAccountResourceId string

resource searchService 'Microsoft.Search/searchServices@2025-05-01' = {
  name: searchServiceName
  location: location
  tags: tags
  sku: {
    name: 'basic'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    disableLocalAuth: true
    hostingMode: 'Default'
    networkRuleSet: {
      ipRules: []
    }
    partitionCount: 1
    publicNetworkAccess: 'enabled'
    replicaCount: 1
    semanticSearch: 'free'
  }
}

resource cosmosSharedPrivateLink 'Microsoft.Search/searchServices/sharedPrivateLinkResources@2025-05-01' = {
  name: 'cosmos-products'
  parent: searchService
  properties: {
    groupId: 'Sql'
    privateLinkResourceId: cosmosAccountResourceId
    requestMessage: 'Approve private indexer access from the TJX retail Search service.'
  }
}

output endpoint string = searchService.properties.endpoint
output name string = searchService.name
output resourceId string = searchService.id
output systemAssignedPrincipalId string = searchService.identity.principalId

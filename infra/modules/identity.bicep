@description('Name of the application user-assigned managed identity.')
param identityName string

@description('Azure region for the managed identity.')
param location string

@description('Tags assigned to the managed identity.')
param tags object

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
  tags: tags
}

output clientId string = identity.properties.clientId
output name string = identity.name
output principalId string = identity.properties.principalId
output resourceId string = identity.id

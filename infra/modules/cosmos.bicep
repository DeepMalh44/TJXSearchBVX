@description('Name of the Cosmos DB account created for the POC.')
param cosmosAccountName string

@description('Azure region for the Cosmos DB account.')
param location string

@description('Tags assigned to the Cosmos DB account.')
param tags object

module cosmosAccount 'br/public:avm/res/document-db/database-account:0.21.1' = {
  name: 'cosmos-account'
  params: {
    name: cosmosAccountName
    location: location
    tags: union(tags, {
      Security: 'Exception'
      SecurityControl: 'Ignore'
    })
    capacityMode: 'Serverless'
    disableKeyBasedMetadataWriteAccess: true
    disableLocalAuthentication: true
    enableAutomaticFailover: false
    enableBurstCapacity: false
    enableTelemetry: false
    failoverLocations: [
      {
        failoverPriority: 0
        isZoneRedundant: false
        locationName: location
      }
    ]
    networkRestrictions: {
      ipRules: []
      networkAclBypass: 'None'
      publicNetworkAccess: 'Disabled'
      virtualNetworkRules: []
    }
    sqlDatabases: [
      {
        name: 'retail-search-poc'
        containers: [
          {
            name: 'products'
            paths: [
              '/category'
            ]
          }
        ]
      }
    ]
    zoneRedundant: false
  }
}

output endpoint string = cosmosAccount.outputs.endpoint
output name string = cosmosAccount.outputs.name
output resourceId string = cosmosAccount.outputs.resourceId

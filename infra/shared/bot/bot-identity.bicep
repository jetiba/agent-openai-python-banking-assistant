@description('The name of the User Assigned Managed Identity for the bot')
param name string

@description('The location for the managed identity')
param location string

@description('Tags to apply to the resource')
param tags object = {}

// User Assigned Managed Identity for Azure Bot
resource botManagedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
  tags: tags
}

// Outputs
output identityId string = botManagedIdentity.id
output clientId string = botManagedIdentity.properties.clientId
output principalId string = botManagedIdentity.properties.principalId
output name string = botManagedIdentity.name

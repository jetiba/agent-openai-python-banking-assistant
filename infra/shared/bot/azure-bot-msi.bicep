@description('The name of the Azure Bot resource')
param name string

@description('The location for the Azure Bot resource (global is recommended)')
param location string = 'global'

@description('Tags to apply to the resource')
param tags object = {}

@description('The Microsoft App ID - for UserAssignedMSI, this is the client ID of the managed identity')
param microsoftAppId string

@description('The Microsoft App Tenant ID (required for UserAssignedMSI)')
param microsoftAppTenantId string

@description('The resource ID of the User Assigned Managed Identity (required for UserAssignedMSI)')
param userAssignedManagedIdentityId string

@description('The messaging endpoint for the bot (your backend /api/messages URL)')
param messagingEndpoint string

@description('The SKU of the Azure Bot')
@allowed([
  'F0'
  'S1'
])
param sku string = 'F0'

@description('The display name shown in Teams chats')
param displayName string = 'Banking Assistant'

@description('Enable Microsoft Teams channel')
param enableTeamsChannel bool = false

// M365 Extensions channel is currently in preview and may not work in all tenants/regions
// Set to false by default to avoid deployment failures
@description('Enable Copilot channel (M365 Extensions) - requires preview enrollment')
param enableM365ExtensionsChannel bool = false

// Azure Bot Service with User Assigned Managed Identity
resource azureBot 'Microsoft.BotService/botServices@2022-09-15' = {
  name: name
  location: location
  tags: tags
  kind: 'azurebot'
  sku: {
    name: sku
  }
  properties: {
    displayName: displayName
    description: 'Banking Assistant Bot for Teams and Copilot'
    iconUrl: 'https://docs.botframework.com/static/devportal/client/images/bot-framework-default.png'
    endpoint: messagingEndpoint
    msaAppId: microsoftAppId
    msaAppTenantId: microsoftAppTenantId
    msaAppType: 'UserAssignedMSI'
    msaAppMSIResourceId: userAssignedManagedIdentityId
    luisAppIds: []
    isCmekEnabled: false
    disableLocalAuth: false
    schemaTransformationVersion: '1.3'
  }
}

// Microsoft Teams Channel
resource teamsChannel 'Microsoft.BotService/botServices/channels@2022-09-15' = if (enableTeamsChannel) {
  parent: azureBot
  name: 'MsTeamsChannel'
  location: location
  properties: {
    channelName: 'MsTeamsChannel'
    properties: {
      enableCalling: false
      isEnabled: true
    }
  }
}

// M365 Extensions Channel (for Copilot)
resource m365ExtensionsChannel 'Microsoft.BotService/botServices/channels@2022-09-15' = if (enableM365ExtensionsChannel) {
  parent: azureBot
  name: 'M365Extensions'
  location: location
}

// Outputs
output botId string = azureBot.id
output botName string = azureBot.name
output botEndpoint string = azureBot.properties.endpoint
output msaAppId string = microsoftAppId

@description('The name of the Azure Bot resource')
param name string

@description('The location for the Azure Bot resource (global is recommended)')
param location string = 'global'

@description('Tags to apply to the resource')
param tags object = {}

@description('The Microsoft App ID from Azure AD App Registration')
param microsoftAppId string

@description('The Microsoft App Tenant ID (for single-tenant bots)')
param microsoftAppTenantId string = ''

@description('The type of Microsoft App: MultiTenant, SingleTenant, or UserAssignedMSI')
@allowed([
  'MultiTenant'
  'SingleTenant'
  'UserAssignedMSI'
])
param microsoftAppType string = 'MultiTenant'

@description('The messaging endpoint for the bot (your backend /api/messages URL)')
param messagingEndpoint string

@description('The SKU of the Azure Bot')
@allowed([
  'F0'
  'S1'
])
param sku string = 'F0'

@description('Enable Microsoft Teams channel')
param enableTeamsChannel bool = true

@description('Enable Copilot channel (M365 Extensions)')
param enableM365ExtensionsChannel bool = true

// Azure Bot Service
resource azureBot 'Microsoft.BotService/botServices@2022-09-15' = {
  name: name
  location: location
  tags: tags
  kind: 'azurebot'
  sku: {
    name: sku
  }
  properties: {
    displayName: name
    description: 'Banking Assistant Bot for Teams and Copilot'
    iconUrl: 'https://docs.botframework.com/static/devportal/client/images/bot-framework-default.png'
    endpoint: messagingEndpoint
    msaAppId: microsoftAppId
    msaAppTenantId: microsoftAppType == 'SingleTenant' ? microsoftAppTenantId : null
    msaAppType: microsoftAppType
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

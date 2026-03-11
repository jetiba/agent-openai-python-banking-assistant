// ---------------------------------------------------------------------------
// Lab 9 – MCP Tool Integration
// Resources: everything from Lab 8 + MCP URL env vars on the backend
// ---------------------------------------------------------------------------

targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

param resourceGroupName string = ''
param applicationInsightsName string = ''
param applicationInsightsDashboardName string = ''
param logAnalyticsName string = ''
param containerAppsEnvironmentName string = ''
param containerRegistryName string = ''
param keyVaultName string = ''
param accountContainerAppName string = ''
param accountAppExists bool = false
param transactionContainerAppName string = ''
param transactionAppExists bool = false
param paymentContainerAppName string = ''
param paymentAppExists bool = false
param webContainerAppName string = ''
param webAppExists bool = false

// ---- Lab 5: Easy Auth (optional) ----
@description('Microsoft Entra ID client (application) ID for Easy Auth on the web frontend. Leave empty to skip Easy Auth.')
param webAuthClientId string = ''
@secure()
@description('Microsoft Entra ID client secret for Easy Auth. Required when webAuthClientId is set.')
param webAuthClientSecret string = ''

// ---- Lab 7: AI Foundry ----
@description('The Azure AI Foundry resource group name. If omitted will use the main resource group.')
param foundryResourceGroupName string = ''

@description('The Azure AI Foundry resource name. If omitted will be generated.')
param foundryResourceName string = ''

@description('The Azure AI Foundry Project name. If omitted will be generated.')
param aiProjectName string = ''

@description('Location for the Foundry resource group')
@allowed([
  'australiaeast'
  'brazilsouth'
  'canadaeast'
  'eastus'
  'eastus2'
  'francecentral'
  'germanywestcentral'
  'japaneast'
  'koreacentral'
  'northcentralus'
  'norwayeast'
  'polandcentral'
  'southafricanorth'
  'southcentralus'
  'southindia'
  'spaincentral'
  'swedencentral'
  'switzerlandnorth'
  'uksouth'
  'westeurope'
  'westus'
  'westus3'
])
@metadata({
  azd: {
    type: 'location'
  }
})
param foundryResourceGroupLocation string = 'eastus'

@description('Array of models to deploy')
param models array = [
  {
    deploymentName: 'gpt-4.1'
    name: 'gpt-4.1'
    format: 'OpenAI'
    version: '2025-04-14'
    skuName: 'GlobalStandard'
    capacity: 120
  }
]

// ---- Lab 7: Backend AI Service ----
param backendContainerAppName string = ''
param backendAppExists bool = false

// ---- Lab 8: Storage Account ----
param storageAccountName string = ''
param storageResourceGroupName string = ''
param storageResourceGroupLocation string = location
param storageContainerName string = 'content'
param storageSkuName string // Set in main.parameters.json

// ---- Lab 8: Document Intelligence ----
param documentIntelligenceServiceName string = ''
param documentIntelligenceResourceGroupName string = ''
// Document Intelligence new REST API available in eastus, westus2, westeurope, switzerlandnorth.
// https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/sdk-overview-v4-0
@allowed(['eastus', 'westus2', 'westeurope', 'switzerlandnorth'])
param documentIntelligenceResourceGroupLocation string = 'eastus'
param documentIntelligenceSkuName string = 'S0'

var abbrs = loadJsonContent('./shared/abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }

// ---------------------------------------------------------------------------
// Resource Groups
// ---------------------------------------------------------------------------
resource resourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: !empty(resourceGroupName) ? resourceGroupName : '${abbrs.resourcesResourceGroups}${environmentName}'
  location: location
  tags: tags
}

resource foundryResourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' existing = if (!empty(foundryResourceGroupName)) {
  name: !empty(foundryResourceGroupName) ? foundryResourceGroupName : resourceGroup.name
}

resource documentIntelligenceResourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' existing = if (!empty(documentIntelligenceResourceGroupName)) {
  name: !empty(documentIntelligenceResourceGroupName) ? documentIntelligenceResourceGroupName : resourceGroup.name
}

resource storageResourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' existing = if (!empty(storageResourceGroupName)) {
  name: !empty(storageResourceGroupName) ? storageResourceGroupName : resourceGroup.name
}

// ---------------------------------------------------------------------------
// Monitoring  (Log Analytics + Application Insights + Dashboard)
// ---------------------------------------------------------------------------
module monitoring './shared/monitor/monitoring.bicep' = {
  name: 'monitoring'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    applicationInsightsName: !empty(applicationInsightsName) ? applicationInsightsName : '${abbrs.insightsComponents}${resourceToken}'
    logAnalyticsName: !empty(logAnalyticsName) ? logAnalyticsName : '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    applicationInsightsDashboardName: !empty(applicationInsightsDashboardName) ? applicationInsightsDashboardName : '${abbrs.portalDashboards}${resourceToken}'
  }
}

// ---------------------------------------------------------------------------
// Container Apps  (ACR + ACA Environment)
// ---------------------------------------------------------------------------
module containerApps './shared/host/container-apps.bicep' = {
  name: 'container-apps'
  scope: resourceGroup
  params: {
    name: 'app'
    location: location
    tags: tags
    containerAppsEnvironmentName: !empty(containerAppsEnvironmentName) ? containerAppsEnvironmentName : '${abbrs.appManagedEnvironments}${resourceToken}'
    containerRegistryName: !empty(containerRegistryName) ? containerRegistryName : '${abbrs.containerRegistryRegistries}${resourceToken}'
    logAnalyticsWorkspaceName: monitoring.outputs.logAnalyticsWorkspaceName
    applicationInsightsName: monitoring.outputs.applicationInsightsName
  }
}

// ---------------------------------------------------------------------------
// Key Vault  (from Lab 5)
// ---------------------------------------------------------------------------
var kvName = !empty(keyVaultName) ? keyVaultName : '${abbrs.keyVaultVaults}${resourceToken}'

module keyVault './shared/security/keyvault.bicep' = {
  name: 'key-vault'
  scope: resourceGroup
  params: {
    name: kvName
    location: location
    tags: tags
  }
}

module appInsightsSecret './shared/security/keyvault-secret.bicep' = {
  name: 'appinsights-secret'
  scope: resourceGroup
  params: {
    name: 'appinsights-connection-string'
    keyVaultName: keyVault.outputs.name
    secretValue: monitoring.outputs.applicationInsightsConnectionString
    contentType: 'text/plain'
  }
}

// ---------------------------------------------------------------------------
// Lab 7: Azure AI Foundry  (Account + Project + Model Deployment)
// ---------------------------------------------------------------------------
module aiFoundry './shared/ai/foundry.bicep' = {
  name: 'ai-foundry'
  scope: foundryResourceGroup
  params: {
    aiProjectName: !empty(aiProjectName) ? aiProjectName : 'proj-${resourceToken}'
    aiProjectFriendlyName: 'Banking Assistant Project'
    aiProjectDescription: 'Project for the Banking Assistant Copilot using Azure AI Foundry'
    foundryResourceName: !empty(foundryResourceName) ? foundryResourceName : 'foundry-${resourceToken}'
    location: foundryResourceGroupLocation
    tags: tags
  }
}

@batchSize(1)
module foundryModelDeployments './shared/ai/foundry-model-deployment.bicep' = [for (model, index) in models: {
  name: 'foundry-model-deployment-${model.name}-${index}'
  scope: foundryResourceGroup
  params: {
    foundryResourceName: aiFoundry.outputs.accountName
    deploymentName: model.deploymentName
    modelName: model.name
    modelFormat: model.format
    modelVersion: model.version
    modelSkuName: model.skuName
    modelCapacity: model.capacity
    tags: tags
  }
}]

// ---------------------------------------------------------------------------
// Lab 8: Document Intelligence  (Cognitive Services – FormRecognizer)
// ---------------------------------------------------------------------------
module documentIntelligence './shared/ai/cognitiveservices.bicep' = {
  name: 'documentIntelligence'
  scope: documentIntelligenceResourceGroup
  params: {
    name: !empty(documentIntelligenceServiceName) ? documentIntelligenceServiceName : '${abbrs.cognitiveServicesFormRecognizer}${resourceToken}'
    kind: 'FormRecognizer'
    location: documentIntelligenceResourceGroupLocation
    tags: tags
    sku: {
      name: documentIntelligenceSkuName
    }
  }
}

// ---------------------------------------------------------------------------
// Lab 8: Storage Account  (Blob – for uploaded invoices)
// ---------------------------------------------------------------------------
module storage './shared/storage/storage-account.bicep' = {
  name: 'storage'
  scope: storageResourceGroup
  params: {
    name: !empty(storageAccountName) ? storageAccountName : '${abbrs.storageStorageAccounts}${resourceToken}'
    location: storageResourceGroupLocation
    tags: tags
    allowBlobPublicAccess: false
    publicNetworkAccess: 'Enabled'
    sku: {
      name: storageSkuName
    }
    deleteRetentionPolicy: {
      enabled: true
      days: 2
    }
    containers: [
      {
        name: storageContainerName
        publicAccess: 'None'
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Backend AI Service  (Container App) — updated env vars for Lab 9 (MCP URLs)
// ---------------------------------------------------------------------------
module backend 'app/backend.bicep' = {
  name: 'backend'
  scope: resourceGroup
  params: {
    name: !empty(backendContainerAppName) ? backendContainerAppName : '${abbrs.appContainerApps}backend-${resourceToken}'
    location: location
    tags: tags
    identityName: '${abbrs.managedIdentityUserAssignedIdentities}backend-${resourceToken}'
    applicationInsightsName: monitoring.outputs.applicationInsightsName
    containerAppsEnvironmentName: containerApps.outputs.environmentName
    containerRegistryName: containerApps.outputs.registryName
    corsAcaUrl: ''
    exists: backendAppExists
    env: [
      {
        name: 'AZURE_AI_PROJECT_ENDPOINT'
        value: '${aiFoundry.outputs.endpoint}api/projects/${aiFoundry.outputs.aiProjectName}/'
      }
      {
        name: 'AZURE_AI_MODEL_DEPLOYMENT_NAME'
        value: models[0].deploymentName
      }
      {
        name: 'AZURE_OPENAI_ENDPOINT'
        value: aiFoundry.outputs.openAIEndpoint
      }
      {
        name: 'AZURE_STORAGE_ACCOUNT'
        value: storage.outputs.name
      }
      {
        name: 'AZURE_STORAGE_CONTAINER'
        value: storageContainerName
      }
      {
        name: 'AZURE_DOCUMENT_INTELLIGENCE_SERVICE'
        value: documentIntelligence.outputs.name
      }
      // ---- NEW in Lab 9: MCP server URLs for the business APIs ----
      {
        name: 'ACCOUNT_API_MCP_URL'
        value: '${account.outputs.SERVICE_API_URI}/mcp/'
      }
      {
        name: 'TRANSACTION_API_MCP_URL'
        value: '${transaction.outputs.SERVICE_API_URI}/mcp/'
      }
      {
        name: 'PAYMENT_API_MCP_URL'
        value: '${payment.outputs.SERVICE_API_URI}/mcp/'
      }
    ]
  }
}

// ---- RBAC: Grant backend identity access to AI Foundry ----
module foundryCognitiveUserRoleBackend './shared/security/role.bicep' = {
  scope: foundryResourceGroup
  name: 'foundry-cognitive-user-role-backend'
  params: {
    principalId: backend.outputs.SERVICE_API_IDENTITY_PRINCIPAL_ID
    roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services User
    principalType: 'ServicePrincipal'
  }
}

module foundryAIDeveloperRoleBackend './shared/security/role.bicep' = {
  scope: foundryResourceGroup
  name: 'foundry-ai-developer-role-backend'
  params: {
    principalId: backend.outputs.SERVICE_API_IDENTITY_PRINCIPAL_ID
    roleDefinitionId: '64702f94-c441-49e6-a78b-ef80e0188fee' // AI Developer
    principalType: 'ServicePrincipal'
  }
}

// ---- Lab 8: RBAC for Storage Blob Data Contributor ----
module storageRoleBackend './shared/security/role.bicep' = {
  scope: storageResourceGroup
  name: 'storage-role-backend'
  params: {
    principalId: backend.outputs.SERVICE_API_IDENTITY_PRINCIPAL_ID
    roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
    principalType: 'ServicePrincipal'
  }
}

// ---- Lab 8: RBAC for Document Intelligence ----
module documentIntelligenceRoleBackend './shared/security/role.bicep' = {
  scope: documentIntelligenceResourceGroup
  name: 'documentIntelligence-role-backend'
  params: {
    principalId: backend.outputs.SERVICE_API_IDENTITY_PRINCIPAL_ID
    roleDefinitionId: 'a97b65f3-24c7-4388-baec-2e87135dc908' // Cognitive Services User (for Document Intelligence)
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Account API
// ---------------------------------------------------------------------------
module account 'app/account.bicep' = {
  name: 'account'
  scope: resourceGroup
  params: {
    name: !empty(accountContainerAppName) ? accountContainerAppName : '${abbrs.appContainerApps}account-${resourceToken}'
    location: location
    tags: tags
    identityName: '${abbrs.managedIdentityUserAssignedIdentities}account-${resourceToken}'
    applicationInsightsName: monitoring.outputs.applicationInsightsName
    containerAppsEnvironmentName: containerApps.outputs.environmentName
    containerRegistryName: containerApps.outputs.registryName
    corsAcaUrl: ''
    exists: accountAppExists
    keyVaultEndpoint: keyVault.outputs.endpoint
  }
}

module accountKeyVaultAccess './shared/security/keyvault-access.bicep' = {
  name: 'account-keyvault-access'
  scope: resourceGroup
  params: {
    keyVaultName: keyVault.outputs.name
    principalId: account.outputs.SERVICE_API_IDENTITY_PRINCIPAL_ID
  }
}

// ---------------------------------------------------------------------------
// Transaction API
// ---------------------------------------------------------------------------
module transaction 'app/transaction.bicep' = {
  name: 'transaction'
  scope: resourceGroup
  params: {
    name: !empty(transactionContainerAppName) ? transactionContainerAppName : '${abbrs.appContainerApps}transaction-${resourceToken}'
    location: location
    tags: tags
    identityName: '${abbrs.managedIdentityUserAssignedIdentities}transaction-${resourceToken}'
    applicationInsightsName: monitoring.outputs.applicationInsightsName
    containerAppsEnvironmentName: containerApps.outputs.environmentName
    containerRegistryName: containerApps.outputs.registryName
    corsAcaUrl: ''
    exists: transactionAppExists
    keyVaultEndpoint: keyVault.outputs.endpoint
  }
}

module transactionKeyVaultAccess './shared/security/keyvault-access.bicep' = {
  name: 'transaction-keyvault-access'
  scope: resourceGroup
  params: {
    keyVaultName: keyVault.outputs.name
    principalId: transaction.outputs.SERVICE_API_IDENTITY_PRINCIPAL_ID
  }
}

// ---------------------------------------------------------------------------
// Payment API
// ---------------------------------------------------------------------------
module payment 'app/payment.bicep' = {
  name: 'payment'
  scope: resourceGroup
  params: {
    name: !empty(paymentContainerAppName) ? paymentContainerAppName : '${abbrs.appContainerApps}payment-${resourceToken}'
    location: location
    tags: tags
    identityName: '${abbrs.managedIdentityUserAssignedIdentities}payment-${resourceToken}'
    applicationInsightsName: monitoring.outputs.applicationInsightsName
    containerAppsEnvironmentName: containerApps.outputs.environmentName
    containerRegistryName: containerApps.outputs.registryName
    corsAcaUrl: ''
    exists: paymentAppExists
    transactionApiUrl: transaction.outputs.SERVICE_API_URI
    keyVaultEndpoint: keyVault.outputs.endpoint
  }
}

module paymentKeyVaultAccess './shared/security/keyvault-access.bicep' = {
  name: 'payment-keyvault-access'
  scope: resourceGroup
  params: {
    keyVaultName: keyVault.outputs.name
    principalId: payment.outputs.SERVICE_API_IDENTITY_PRINCIPAL_ID
  }
}

// ---------------------------------------------------------------------------
// Web Frontend  (proxy /chatkit, /upload, /preview to backend)
// ---------------------------------------------------------------------------
module web 'app/web.bicep' = {
  name: 'web'
  scope: resourceGroup
  params: {
    name: !empty(webContainerAppName) ? webContainerAppName : '${abbrs.appContainerApps}web-${resourceToken}'
    location: location
    tags: tags
    identityName: '${abbrs.managedIdentityUserAssignedIdentities}web-${resourceToken}'
    applicationInsightsName: monitoring.outputs.applicationInsightsName
    containerAppsEnvironmentName: containerApps.outputs.environmentName
    containerRegistryName: containerApps.outputs.registryName
    exists: webAppExists
    accountApiUrl: account.outputs.SERVICE_API_URI
    transactionApiUrl: transaction.outputs.SERVICE_API_URI
    paymentApiUrl: payment.outputs.SERVICE_API_URI
    backendApiUrl: backend.outputs.SERVICE_API_URI
    keyVaultEndpoint: keyVault.outputs.endpoint
  }
}

module webKeyVaultAccess './shared/security/keyvault-access.bicep' = {
  name: 'web-keyvault-access'
  scope: resourceGroup
  params: {
    keyVaultName: keyVault.outputs.name
    principalId: web.outputs.SERVICE_WEB_IDENTITY_PRINCIPAL_ID
  }
}

// ---- Lab 5: Easy Auth for Web Frontend (optional) ----
module webAuth './shared/security/container-app-auth.bicep' = if (!empty(webAuthClientId)) {
  name: 'web-auth'
  scope: resourceGroup
  params: {
    containerAppName: web.outputs.SERVICE_WEB_NAME
    clientId: webAuthClientId
    clientSecretValue: webAuthClientSecret
    issuerUrl: '${environment().authentication.loginEndpoint}${tenant().tenantId}/v2.0'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = resourceGroup.name
output AZURE_CONTAINER_ENVIRONMENT_NAME string = containerApps.outputs.environmentName
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerApps.outputs.registryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerApps.outputs.registryName
output AZURE_KEY_VAULT_NAME string = keyVault.outputs.name
output AZURE_KEY_VAULT_ENDPOINT string = keyVault.outputs.endpoint
output ACCOUNT_API_URL string = account.outputs.SERVICE_API_URI
output TRANSACTION_API_URL string = transaction.outputs.SERVICE_API_URI
output PAYMENT_API_URL string = payment.outputs.SERVICE_API_URI
output WEB_APP_URL string = web.outputs.SERVICE_WEB_URI
output BACKEND_API_URL string = backend.outputs.SERVICE_API_URI
output FOUNDRY_PROJECT_ENDPOINT string = '${aiFoundry.outputs.endpoint}api/projects/${aiFoundry.outputs.aiProjectName}/'
output FOUNDRY_RESOURCE_NAME string = aiFoundry.outputs.accountName
output FOUNDRY_CHATGPT_DEPLOYMENT string = models[0].deploymentName
output AZURE_DOCUMENT_INTELLIGENCE_SERVICE string = documentIntelligence.outputs.name
output AZURE_DOCUMENT_INTELLIGENCE_RESOURCE_GROUP string = documentIntelligenceResourceGroup.name
output AZURE_STORAGE_ACCOUNT string = storage.outputs.name
output AZURE_STORAGE_CONTAINER string = storageContainerName
output AZURE_STORAGE_RESOURCE_GROUP string = storageResourceGroup.name

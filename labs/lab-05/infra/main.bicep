// ---------------------------------------------------------------------------
// Lab 5 – Security: Built-in Authentication & Azure Key Vault
// Resources: everything from Labs 1-4 + Key Vault + Easy Auth
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

// ---- NEW in Lab 5: Easy Auth (optional) ----
@description('Microsoft Entra ID client (application) ID for Easy Auth on the web frontend. Leave empty to skip Easy Auth.')
param webAuthClientId string = ''
@secure()
@description('Microsoft Entra ID client secret for Easy Auth. Required when webAuthClientId is set.')
param webAuthClientSecret string = ''

var abbrs = loadJsonContent('./shared/abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }

// ---------------------------------------------------------------------------
// Resource Group
// ---------------------------------------------------------------------------
resource resourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: !empty(resourceGroupName) ? resourceGroupName : '${abbrs.resourcesResourceGroups}${environmentName}'
  location: location
  tags: tags
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
// NEW in Lab 5: Azure Key Vault
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

// Store Application Insights connection string in Key Vault
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

// Grant Account API access to Key Vault secrets
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

// Grant Transaction API access to Key Vault secrets
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

// Grant Payment API access to Key Vault secrets
module paymentKeyVaultAccess './shared/security/keyvault-access.bicep' = {
  name: 'payment-keyvault-access'
  scope: resourceGroup
  params: {
    keyVaultName: keyVault.outputs.name
    principalId: payment.outputs.SERVICE_API_IDENTITY_PRINCIPAL_ID
  }
}

// ---------------------------------------------------------------------------
// Web Frontend
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
    keyVaultEndpoint: keyVault.outputs.endpoint
  }
}

// Grant Web Frontend access to Key Vault secrets
module webKeyVaultAccess './shared/security/keyvault-access.bicep' = {
  name: 'web-keyvault-access'
  scope: resourceGroup
  params: {
    keyVaultName: keyVault.outputs.name
    principalId: web.outputs.SERVICE_WEB_IDENTITY_PRINCIPAL_ID
  }
}

// ---------------------------------------------------------------------------
// NEW in Lab 5: Easy Auth for Web Frontend (optional)
// Deploys Microsoft Entra ID authentication when a client ID is provided.
// ---------------------------------------------------------------------------
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

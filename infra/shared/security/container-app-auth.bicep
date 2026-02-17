metadata description = 'Configures built-in authentication (Easy Auth) for an Azure Container App using Microsoft Entra ID.'

@description('Name of the existing Container App to protect')
param containerAppName string

@description('Microsoft Entra ID application (client) ID')
param clientId string

@secure()
@description('Microsoft Entra ID client secret value')
param clientSecretValue string

@description('Issuer URL, e.g. https://login.microsoftonline.com/{tenant-id}/v2.0')
param issuerUrl string

@description('Action to take when an unauthenticated request is received')
@allowed([ 'RedirectToLoginPage', 'Return401', 'Return403', 'AllowAnonymous' ])
param unauthenticatedAction string = 'RedirectToLoginPage'

resource containerApp 'Microsoft.App/containerApps@2023-05-02-preview' existing = {
  name: containerAppName
}

resource authConfig 'Microsoft.App/containerApps/authConfigs@2023-05-02-preview' = {
  name: 'current'
  parent: containerApp
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      unauthenticatedClientAction: unauthenticatedAction
    }
    identityProviders: {
      azureActiveDirectory: {
        registration: {
          clientId: clientId
          clientSecretSettingName: 'microsoft-provider-authentication-secret'
          openIdIssuer: issuerUrl
        }
        validation: {
          allowedAudiences: [
            'api://${clientId}'
          ]
        }
      }
    }
    login: {
      tokenStore: {
        enabled: true
      }
    }
  }
}

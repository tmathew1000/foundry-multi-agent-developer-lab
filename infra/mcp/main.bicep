targetScope = 'resourceGroup'

@minLength(1)
@maxLength(64)
@description('The azd environment name used to generate unique resource names.')
param environmentName string

@description('The Azure region for the MCP hosting resources.')
param location string = resourceGroup().location

var resourceToken = toLower(uniqueString(subscription().id, resourceGroup().id, environmentName))
var tags = {
  'azd-env-name': environmentName
}
var registryName = take('cr${replace(environmentName, '-', '')}${resourceToken}', 50)
var identityName = 'id-mcp-${resourceToken}'
var logAnalyticsName = 'log-mcp-${resourceToken}'
var applicationInsightsName = 'appi-mcp-${resourceToken}'
var containerAppsEnvironmentName = 'cae-mcp-${resourceToken}'
var containerAppName = 'ca-mcp-${resourceToken}'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    IngestionMode: 'LogAnalytics'
    WorkspaceResourceId: logAnalytics.id
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: registryName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource mcpIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
  tags: tags
}

var acrPullRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'
)

resource registryPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, mcpIdentity.id, acrPullRoleDefinitionId)
  scope: registry
  properties: {
    principalId: mcpIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-10-02-preview' = {
  name: containerAppsEnvironmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource mcpServer 'Microsoft.App/containerApps@2024-10-02-preview' = {
  name: containerAppName
  location: location
  tags: union(tags, {
    'azd-service-name': 'mcp-server'
  })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${mcpIdentity.id}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          identity: mcpIdentity.id
          server: registry.properties.loginServer
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'mcp-server'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          env: [
            {
              name: 'MCP_HOST'
              value: '0.0.0.0'
            }
            {
              name: 'MCP_PORT'
              value: '8000'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
  dependsOn: [
    registryPullAssignment
  ]
}

output APPLICATIONINSIGHTS_CONNECTION_STRING string = applicationInsights.properties.ConnectionString
output AZURE_APPLICATION_INSIGHTS_NAME string = applicationInsights.name
output AZURE_CONTAINER_APPS_ENVIRONMENT_NAME string = containerAppsEnvironment.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = registry.properties.loginServer
output AZURE_CONTAINER_REGISTRY_NAME string = registry.name
output AZURE_CONTAINER_REGISTRY_RESOURCE_ID string = registry.id
output SERVICE_MCP_SERVER_NAME string = mcpServer.name
output SERVICE_MCP_SERVER_RESOURCE_EXISTS bool = true
output SERVICE_MCP_SERVER_URI string = 'https://${mcpServer.properties.configuration.ingress.fqdn}'

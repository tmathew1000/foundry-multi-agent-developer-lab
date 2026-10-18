targetScope = 'resourceGroup'

@minLength(1)
@maxLength(64)
@description('The azd environment name used to generate unique resource names.')
param environmentName string

@description('The Azure region for Search and Storage.')
param location string = resourceGroup().location

@description('The signed-in principal that runs azd provision.')
param principalId string

@description('The full ARM resource ID of the Microsoft Foundry project.')
param projectResourceId string

@description('Chat deployment name, matching the ai-project deployment in azure.yaml.')
param chatDeploymentName string = 'travel-model'

var projectIdParts = split(projectResourceId, '/')
var projectSubscriptionId = projectIdParts[2]
var projectResourceGroupName = projectIdParts[4]
var foundryAccountName = projectIdParts[8]
var resourceToken = toLower(uniqueString(subscription().id, resourceGroup().id, environmentName))
var searchName = take('srch-${environmentName}-${resourceToken}', 60)
var storageName = take('st${replace(environmentName, '-', '')}${resourceToken}', 24)
var containerName = 'travel-knowledge'
var knowledgeSourceName = 'travel-destinations-blob'
var knowledgeBaseName = 'travel-destinations'
var tags = {
  'azd-env-name': environmentName
  workload: 'foundry-iq'
}

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
  scope: resourceGroup(projectSubscriptionId, projectResourceGroupName)
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource knowledgeContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: containerName
  properties: {
    publicAccess: 'None'
  }
}

resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: searchName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'basic'
  }
  properties: {
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
    disableLocalAuth: false
    hostingMode: 'Default'
    publicNetworkAccess: 'enabled'
    replicaCount: 1
    semanticSearch: 'standard'
    partitionCount: 1
  }
}

var storageBlobDataReaderRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
)
var storageBlobDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
)
var cognitiveServicesUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'a97b65f3-24c7-4388-baec-2e87135dc908'
)
var searchServiceContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
)
var searchIndexDataReaderRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '1407120a-92aa-4202-b7e9-c0e197c71c8f'
)

resource searchReadsKnowledge 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, search.id, storageBlobDataReaderRoleId)
  scope: storage
  properties: {
    principalId: search.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataReaderRoleId
  }
}

module searchFoundryAccess 'foundry-access.bicep' = {
  name: 'foundry-iq-model-access'
  scope: resourceGroup(projectSubscriptionId, projectResourceGroupName)
  params: {
    foundryAccountName: foundryAccount.name
    principalId: search.identity.principalId
    roleDefinitionId: cognitiveServicesUserRoleId
  }
}

resource deployerWritesKnowledge 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, principalId, storageBlobDataContributorRoleId)
  scope: storage
  properties: {
    principalId: principalId
    principalType: 'User'
    roleDefinitionId: storageBlobDataContributorRoleId
  }
}

resource deployerConfiguresSearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, principalId, searchServiceContributorRoleId)
  scope: search
  properties: {
    principalId: principalId
    principalType: 'User'
    roleDefinitionId: searchServiceContributorRoleId
  }
}

resource deployerQueriesSearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, principalId, searchIndexDataReaderRoleId)
  scope: search
  properties: {
    principalId: principalId
    principalType: 'User'
    roleDefinitionId: searchIndexDataReaderRoleId
  }
}

resource foundryRuntimeQueriesSearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, foundryAccount.id, searchIndexDataReaderRoleId)
  scope: search
  properties: {
    principalId: foundryAccount.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: searchIndexDataReaderRoleId
  }
}

output FOUNDRY_IQ_API_VERSION string = '2026-08-01-preview'
output AZURE_AI_MODEL_DEPLOYMENT_NAME string = chatDeploymentName
output FOUNDRY_IQ_CHAT_DEPLOYMENT_NAME string = chatDeploymentName
output FOUNDRY_IQ_EMBEDDING_DEPLOYMENT_NAME string = 'travel-embeddings'
output FOUNDRY_IQ_KNOWLEDGE_BASE string = knowledgeBaseName
output FOUNDRY_IQ_KNOWLEDGE_CONTAINER string = knowledgeContainer.name
output FOUNDRY_IQ_KNOWLEDGE_SOURCE string = knowledgeSourceName
output FOUNDRY_IQ_MODEL_RESOURCE_URI string = 'https://${foundryAccount.name}.services.ai.azure.com'
output FOUNDRY_IQ_SEARCH_ENDPOINT string = 'https://${search.name}.search.windows.net'
output FOUNDRY_IQ_SEARCH_NAME string = search.name
output FOUNDRY_IQ_STORAGE_ACCOUNT_NAME string = storage.name
output FOUNDRY_IQ_STORAGE_RESOURCE_ID string = storage.id

targetScope = 'resourceGroup'

@description('The existing Microsoft Foundry account name.')
param foundryAccountName string

@description('The Azure AI Search managed identity principal ID.')
param principalId string

@description('The Cognitive Services User role definition resource ID.')
param roleDefinitionId string

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource searchUsesFoundryModels 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryAccount.id, principalId, roleDefinitionId)
  scope: foundryAccount
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionId
  }
}

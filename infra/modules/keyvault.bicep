// Key Vault — only for secrets that genuinely cannot be replaced by managed
// identity (third-party API keys, signing keys). RBAC data plane, soft-delete
// and purge protection on, public network access off, private endpoint only.

param names object
param location string
param tags object
param tenantId string

@description('Managed identity principal id granted secret read.')
param principalId string
param dataSubnetId string
param privateDnsZoneId string

var keyVaultSecretsUser = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4633458b-17de-408a-b874-0445c86b69e6'
)

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: names.keyVault
  location: location
  tags: tags
  properties: {
    tenantId: tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}

resource secretsUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, principalId, 'kv-secrets-user')
  scope: vault
  properties: {
    roleDefinitionId: keyVaultSecretsUser
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: '${names.keyVault}-pe'
  location: location
  tags: tags
  properties: {
    subnet: { id: dataSubnetId }
    privateLinkServiceConnections: [
      {
        name: 'kv'
        properties: {
          privateLinkServiceId: vault.id
          groupIds: ['vault']
        }
      }
    ]
  }
}

resource dnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = {
  parent: privateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'vaultcore'
        properties: { privateDnsZoneId: privateDnsZoneId }
      }
    ]
  }
}

output name string = vault.name
output uri string = vault.properties.vaultUri

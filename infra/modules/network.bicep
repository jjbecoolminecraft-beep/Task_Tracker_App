// Single VNet per environment (spec §6.2):
//   snet-aca   — Container Apps environment (delegated)
//   snet-data  — private endpoints for PostgreSQL, Redis, Blob, Key Vault
//   snet-mgmt  — reserved for future bastion / build agents
// Private DNS zones resolve every PaaS name to its private endpoint.

param names object
param location string
param tags object

param vnetAddressSpace string = '10.40.0.0/20'
param acaSubnetPrefix string = '10.40.0.0/23'
param dataSubnetPrefix string = '10.40.2.0/24'
param mgmtSubnetPrefix string = '10.40.3.0/24'

resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: names.vnet
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: [vnetAddressSpace] }
    subnets: [
      {
        name: 'snet-aca'
        properties: {
          addressPrefix: acaSubnetPrefix
          delegations: [
            {
              name: 'aca-delegation'
              properties: { serviceName: 'Microsoft.App/environments' }
            }
          ]
        }
      }
      {
        name: 'snet-data'
        properties: {
          addressPrefix: dataSubnetPrefix
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
      {
        name: 'snet-mgmt'
        properties: { addressPrefix: mgmtSubnetPrefix }
      }
    ]
  }
}

var privateZones = [
  'privatelink.postgres.database.azure.com'
  'privatelink.redis.cache.windows.net'
  'privatelink.blob.core.windows.net'
  'privatelink.vaultcore.azure.net'
]

resource dnsZones 'Microsoft.Network/privateDnsZones@2020-06-01' = [
  for zone in privateZones: {
    name: zone
    location: 'global'
    tags: tags
  }
]

resource dnsLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = [
  for (zone, i) in privateZones: {
    parent: dnsZones[i]
    name: 'link-${names.vnet}'
    location: 'global'
    properties: {
      registrationEnabled: false
      virtualNetwork: { id: vnet.id }
    }
  }
]

output vnetId string = vnet.id
output acaSubnetId string = '${vnet.id}/subnets/snet-aca'
output dataSubnetId string = '${vnet.id}/subnets/snet-data'
output mgmtSubnetId string = '${vnet.id}/subnets/snet-mgmt'
output postgresDnsZoneId string = dnsZones[0].id
output redisDnsZoneId string = dnsZones[1].id
output blobDnsZoneId string = dnsZones[2].id
output keyVaultDnsZoneId string = dnsZones[3].id

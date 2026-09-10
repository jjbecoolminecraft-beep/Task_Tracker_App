// Azure Cache for Redis — session cache, rate limiting, WebSocket fan-out
// (spec §5.1). Non-TLS port disabled, public network access disabled, private
// endpoint only. AAD auth enabled so the API connects with its managed identity.

param names object
param location string
param tags object
param dataSubnetId string
param privateDnsZoneId string

@allowed(['Basic', 'Standard', 'Premium'])
param skuName string = 'Standard'
param skuFamily string = 'C'
param skuCapacity int = 1

resource redis 'Microsoft.Cache/redis@2024-03-01' = {
  name: names.redis
  location: location
  tags: tags
  properties: {
    sku: {
      name: skuName
      family: skuFamily
      capacity: skuCapacity
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Disabled'
    redisConfiguration: {
      'aad-enabled': 'true'
      'maxmemory-policy': 'allkeys-lru'
    }
  }
}

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: '${names.redis}-pe'
  location: location
  tags: tags
  properties: {
    subnet: { id: dataSubnetId }
    privateLinkServiceConnections: [
      {
        name: 'redis'
        properties: {
          privateLinkServiceId: redis.id
          groupIds: ['redisCache']
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
        name: 'redis'
        properties: { privateDnsZoneId: privateDnsZoneId }
      }
    ]
  }
}

output hostName string = redis.properties.hostName

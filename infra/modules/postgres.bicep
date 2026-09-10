// Azure Database for PostgreSQL Flexible Server 16 (spec §5.1, §6.6).
// Entra ID authentication only (no password auth), public access disabled,
// VNet-injected, zone-redundant HA for prod/staging, 35-day PITR geo-redundant.

param names object
param location string
param tags object

@description('Zone-redundant high availability (prod/staging).')
param highAvailability bool

@description('Entra ID group object id set as the AAD administrator.')
param aadAdminObjectId string
param aadAdminName string
param tenantId string

@description('Delegated subnet (Microsoft.DBforPostgreSQL/flexibleServers).')
param delegatedSubnetId string
param privateDnsZoneId string

param skuName string = highAvailability ? 'Standard_D4ds_v5' : 'Standard_D2ds_v5'
param storageSizeGB int = 128

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: names.postgres
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: 'GeneralPurpose'
  }
  properties: {
    version: '16'
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Disabled'
      tenantId: tenantId
    }
    storage: {
      storageSizeGB: storageSizeGB
      autoGrow: 'Enabled'
    }
    backup: {
      backupRetentionDays: 35
      geoRedundantBackup: 'Enabled'
    }
    highAvailability: {
      mode: highAvailability ? 'ZoneRedundant' : 'Disabled'
    }
    network: {
      delegatedSubnetResourceId: delegatedSubnetId
      privateDnsZoneArmResourceId: privateDnsZoneId
      publicNetworkAccess: 'Disabled'
    }
  }
}

resource aadAdmin 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2024-08-01' = {
  parent: server
  name: aadAdminObjectId
  properties: {
    principalType: 'Group'
    principalName: aadAdminName
    tenantId: tenantId
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: server
  name: names.postgresDatabase
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// Full-text search + case-insensitive columns rely on these extensions
// (backend/migrations/versions/0001_initial_schema.py creates citext at runtime).
resource extensions 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2024-08-01' = {
  parent: server
  name: 'azure.extensions'
  properties: {
    value: 'CITEXT,PG_TRGM,UUID-OSSP'
    source: 'user-override'
  }
}

output fqdn string = server.properties.fullyQualifiedDomainName
output databaseName string = database.name

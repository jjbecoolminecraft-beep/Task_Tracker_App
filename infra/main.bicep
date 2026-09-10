// Enterprise Project & Task Tracker — infrastructure entry point (spec §6).
//
// One resource group per environment. Everything data-plane is reachable only
// through private endpoints; no compute resource has a public IP; the API only
// accepts traffic from the Front Door private-link origin. Region is pinned to
// the EU (West Europe primary, North Europe paired) and Azure Policy denies
// anything created elsewhere (infra/policy/allowed-locations.json).

targetScope = 'resourceGroup'

@description('Environment name: dev | test | staging | prod')
@allowed(['dev', 'test', 'staging', 'prod'])
param environment string

@description('Primary region. Must be in the EU Data Boundary.')
@allowed(['westeurope', 'northeurope'])
param location string = 'westeurope'

@description('Short application moniker used in resource names.')
param appName string = 'tasktracker'

@description('Entra ID tenant that owns the application registration.')
param tenantId string = subscription().tenantId

@description('Entra ID group (object id) made PostgreSQL AAD admin — the platform team.')
param postgresAdminGroupObjectId string

@description('Entra ID object id of the API app registration (audience for tokens).')
param apiAppObjectId string = ''

@description('Container image for the API, e.g. <registry>.azurecr.io/api:<sha>.')
param apiImage string

@description('Container image for the background worker.')
param workerImage string

@description('Deploy zone-redundant HA for PostgreSQL (prod/staging only).')
param postgresHighAvailability bool = false

@description('Front Door SKU. Premium adds Private Link origins + managed WAF rules.')
@allowed(['Standard_AzureFrontDoor', 'Premium_AzureFrontDoor'])
param frontDoorSku string = 'Premium_AzureFrontDoor'

var tags = {
  application: appName
  environment: environment
  managedBy: 'bicep'
  dataBoundary: 'eu'
}

module naming 'modules/naming.bicep' = {
  name: 'naming'
  params: {
    appName: appName
    environment: environment
    location: location
  }
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    names: naming.outputs.names
    location: location
    tags: tags
  }
}

module network 'modules/network.bicep' = {
  name: 'network'
  params: {
    names: naming.outputs.names
    location: location
    tags: tags
  }
}

module identity 'modules/identity.bicep' = {
  name: 'identity'
  params: {
    names: naming.outputs.names
    location: location
    tags: tags
  }
}

module keyvault 'modules/keyvault.bicep' = {
  name: 'keyvault'
  params: {
    names: naming.outputs.names
    location: location
    tags: tags
    tenantId: tenantId
    principalId: identity.outputs.principalId
    dataSubnetId: network.outputs.dataSubnetId
    privateDnsZoneId: network.outputs.keyVaultDnsZoneId
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    names: naming.outputs.names
    location: location
    tags: tags
    principalId: identity.outputs.principalId
    dataSubnetId: network.outputs.dataSubnetId
    blobDnsZoneId: network.outputs.blobDnsZoneId
  }
}

module postgres 'modules/postgres.bicep' = {
  name: 'postgres'
  params: {
    names: naming.outputs.names
    location: location
    tags: tags
    highAvailability: postgresHighAvailability
    aadAdminObjectId: postgresAdminGroupObjectId
    aadAdminName: '${appName}-${environment}-pg-admins'
    tenantId: tenantId
    delegatedSubnetId: network.outputs.dataSubnetId
    privateDnsZoneId: network.outputs.postgresDnsZoneId
  }
}

module redis 'modules/redis.bicep' = {
  name: 'redis'
  params: {
    names: naming.outputs.names
    location: location
    tags: tags
    dataSubnetId: network.outputs.dataSubnetId
    privateDnsZoneId: network.outputs.redisDnsZoneId
  }
}

module apps 'modules/containerApps.bicep' = {
  name: 'containerApps'
  params: {
    names: naming.outputs.names
    location: location
    tags: tags
    infraSubnetId: network.outputs.acaSubnetId
    logAnalyticsCustomerId: monitoring.outputs.logAnalyticsCustomerId
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    userAssignedIdentityId: identity.outputs.identityId
    userAssignedClientId: identity.outputs.clientId
    apiImage: apiImage
    workerImage: workerImage
    keyVaultName: keyvault.outputs.name
    postgresFqdn: postgres.outputs.fqdn
    postgresDatabase: postgres.outputs.databaseName
    redisHostName: redis.outputs.hostName
    storageAccountName: storage.outputs.name
    apiAudience: apiAppObjectId
    tenantId: tenantId
  }
}

module web 'modules/staticWebApp.bicep' = {
  name: 'staticWebApp'
  params: {
    names: naming.outputs.names
    location: location
    tags: tags
  }
}

module frontDoor 'modules/frontDoor.bicep' = {
  name: 'frontDoor'
  params: {
    names: naming.outputs.names
    tags: tags
    sku: frontDoorSku
    apiOriginHostName: apps.outputs.apiFqdn
    webOriginHostName: web.outputs.defaultHostName
  }
}

output apiUrl string = 'https://${frontDoor.outputs.endpointHostName}'
output apiInternalFqdn string = apps.outputs.apiFqdn
output postgresFqdn string = postgres.outputs.fqdn
output identityClientId string = identity.outputs.clientId

// One user-assigned managed identity for all service-to-service auth (spec §6.3).
// The API authenticates to PostgreSQL, Blob, Redis and Key Vault as this identity;
// no connection strings or passwords live in application configuration.

param names object
param location string
param tags object

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: names.identity
  location: location
  tags: tags
}

output identityId string = identity.id
output principalId string = identity.properties.principalId
output clientId string = identity.properties.clientId

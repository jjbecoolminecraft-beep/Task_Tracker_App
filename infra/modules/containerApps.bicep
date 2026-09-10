// Container Apps environment (VNet-integrated, internal ingress only) hosting
// three apps: api (FastAPI), worker (Celery/ARQ jobs), scheduler (cron).
// Ingress is internal — only the Front Door private-link origin reaches the API
// (spec §6.2). Service-to-service auth is the user-assigned managed identity;
// connection details are passed as non-secret env vars, secrets via Key Vault.

param names object
param location string
param tags object
param infraSubnetId string
param logAnalyticsCustomerId string
@secure()
param logAnalyticsWorkspaceId string
param appInsightsConnectionString string
param userAssignedIdentityId string
param userAssignedClientId string
param apiImage string
param workerImage string
param keyVaultName string
param postgresFqdn string
param postgresDatabase string
param redisHostName string
param storageAccountName string
param apiAudience string
param tenantId string

param apiMinReplicas int = 2
param apiMaxReplicas int = 10

resource logAnalyticsKeys 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: last(split(logAnalyticsWorkspaceId, '/'))
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: names.acaEnv
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsKeys.listKeys().primarySharedKey
      }
    }
    vnetConfiguration: {
      infrastructureSubnetId: infraSubnetId
      internal: true
    }
    zoneRedundant: true
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

var commonEnv = [
  { name: 'APP_ENV', value: 'prod' }
  { name: 'AZURE_CLIENT_ID', value: userAssignedClientId }
  { name: 'DATABASE_URL', value: 'postgresql+asyncpg://${postgresFqdn}:5432/${postgresDatabase}?ssl=require' }
  { name: 'REDIS_URL', value: 'rediss://${redisHostName}:6380/0' }
  { name: 'BLOB_ACCOUNT_URL', value: 'https://${storageAccountName}.blob.${environment().suffixes.storage}' }
  { name: 'KEY_VAULT_URI', value: 'https://${keyVaultName}${environment().suffixes.keyvaultDns}/' }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
  { name: 'ENTRA_TENANT_ID', value: tenantId }
  { name: 'ENTRA_API_AUDIENCE', value: apiAudience }
  { name: 'DEV_AUTH_ENABLED', value: 'false' }
]

resource api 'Microsoft.App/containerApps@2024-03-01' = {
  name: names.apiApp
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${userAssignedIdentityId}': {} }
  }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      activeRevisionsMode: 'Multiple' // blue/green via traffic-weighted revisions (spec §6.6)
      ingress: {
        external: false
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: apiImage
          resources: { cpu: json('1.0'), memory: '2Gi' }
          env: commonEnv
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/healthz', port: 8000 }
              initialDelaySeconds: 10
              periodSeconds: 15
            }
          ]
        }
      ]
      scale: {
        minReplicas: apiMinReplicas
        maxReplicas: apiMaxReplicas
        rules: [
          {
            name: 'http'
            http: { metadata: { concurrentRequests: '80' } }
          }
        ]
      }
    }
  }
}

resource worker 'Microsoft.App/containerApps@2024-03-01' = {
  name: names.workerApp
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${userAssignedIdentityId}': {} }
  }
  properties: {
    managedEnvironmentId: env.id
    configuration: { activeRevisionsMode: 'Single' }
    template: {
      containers: [
        {
          name: 'worker'
          image: workerImage
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: commonEnv
          command: ['python', '-m', 'app.workers.run']
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 5 }
    }
  }
}

resource scheduler 'Microsoft.App/containerApps@2024-03-01' = {
  name: names.schedulerApp
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${userAssignedIdentityId}': {} }
  }
  properties: {
    managedEnvironmentId: env.id
    configuration: { activeRevisionsMode: 'Single' }
    template: {
      containers: [
        {
          name: 'scheduler'
          image: workerImage
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
          env: commonEnv
          command: ['python', '-m', 'app.workers.scheduler']
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
}

output apiFqdn string = api.properties.configuration.ingress.fqdn

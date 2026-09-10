using '../../main.bicep'

param environment = 'prod'
param location = 'westeurope'
param appName = 'tasktracker'

param postgresAdminGroupObjectId = '00000000-0000-0000-0000-000000000000'
param apiAppObjectId = ''
param apiImage = 'REGISTRY.azurecr.io/task-tracker-api:latest'
param workerImage = 'REGISTRY.azurecr.io/task-tracker-api:latest'

param postgresHighAvailability = true
param frontDoorSku = 'Premium_AzureFrontDoor'

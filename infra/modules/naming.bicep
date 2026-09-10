// Central naming so every module derives resource names the same way.

@description('Short application moniker.')
param appName string

@allowed(['dev', 'test', 'staging', 'prod'])
param environment string

param location string

var loc = {
  westeurope: 'weu'
  northeurope: 'neu'
}[location]

var prefix = '${appName}-${environment}'
// Storage / Key Vault names: no dashes, <= 24 chars, globally unique-ish.
var compact = toLower('${appName}${environment}${loc}')
var suffix = substring(uniqueString(resourceGroup().id), 0, 5)

output names object = {
  prefix: prefix
  vnet: '${prefix}-vnet-${loc}'
  logAnalytics: '${prefix}-log-${loc}'
  appInsights: '${prefix}-appi-${loc}'
  identity: '${prefix}-id-${loc}'
  keyVault: take('${compact}kv${suffix}', 24)
  storage: take('${compact}st${suffix}', 24)
  postgres: '${prefix}-pg-${loc}'
  postgresDatabase: 'tracker'
  redis: '${prefix}-redis-${loc}'
  acaEnv: '${prefix}-cae-${loc}'
  apiApp: '${prefix}-api'
  workerApp: '${prefix}-worker'
  schedulerApp: '${prefix}-scheduler'
  staticWebApp: '${prefix}-web-${loc}'
  frontDoorProfile: '${prefix}-afd'
  frontDoorEndpoint: '${appName}-${environment}'
  wafPolicy: replace('${prefix}waf', '-', '')
}

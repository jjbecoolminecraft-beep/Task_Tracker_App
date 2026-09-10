// Azure Front Door (Premium) + WAF policy (spec §6.1):
// TLS termination, OWASP managed ruleset, DDoS protection, geo-filtering.
// Two origin groups: the SPA (Static Web App) and the API (Container Apps,
// reached via a Private Link origin on Premium).

targetScope = 'resourceGroup'

param names object
param tags object

@allowed(['Standard_AzureFrontDoor', 'Premium_AzureFrontDoor'])
param sku string

param apiOriginHostName string
param webOriginHostName string

resource wafPolicy 'Microsoft.Network/FrontDoorWebApplicationFirewallPolicies@2024-02-01' = {
  name: names.wafPolicy
  location: 'global'
  tags: tags
  sku: { name: sku }
  properties: {
    policySettings: {
      enabledState: 'Enabled'
      mode: 'Prevention'
      requestBodyCheck: 'Enabled'
    }
    managedRules: {
      managedRuleSets: [
        {
          ruleSetType: 'Microsoft_DefaultRuleSet'
          ruleSetVersion: '2.1'
          ruleSetAction: 'Block'
        }
        {
          ruleSetType: 'Microsoft_BotManagerRuleSet'
          ruleSetVersion: '1.0'
        }
      ]
    }
    customRules: {
      rules: [
        {
          name: 'RateLimitPerIp'
          priority: 100
          enabledState: 'Enabled'
          ruleType: 'RateLimitRule'
          rateLimitThreshold: 600
          rateLimitDurationInMinutes: 1
          matchConditions: [
            {
              matchVariable: 'RequestUri'
              operator: 'Contains'
              matchValue: ['/']
            }
          ]
          action: 'Block'
        }
      ]
    }
  }
}

resource profile 'Microsoft.Cdn/profiles@2024-02-01' = {
  name: names.frontDoorProfile
  location: 'global'
  tags: tags
  sku: { name: sku }
}

resource endpoint 'Microsoft.Cdn/profiles/afdEndpoints@2024-02-01' = {
  parent: profile
  name: names.frontDoorEndpoint
  location: 'global'
  properties: { enabledState: 'Enabled' }
}

resource webOriginGroup 'Microsoft.Cdn/profiles/originGroups@2024-02-01' = {
  parent: profile
  name: 'spa'
  properties: {
    loadBalancingSettings: { sampleSize: 4, successfulSamplesRequired: 3 }
    healthProbeSettings: {
      probePath: '/'
      probeProtocol: 'Https'
      probeRequestType: 'HEAD'
      probeIntervalInSeconds: 60
    }
  }
}

resource webOrigin 'Microsoft.Cdn/profiles/originGroups/origins@2024-02-01' = {
  parent: webOriginGroup
  name: 'spa-origin'
  properties: {
    hostName: webOriginHostName
    originHostHeader: webOriginHostName
    httpsPort: 443
    priority: 1
    weight: 1000
    enabledState: 'Enabled'
  }
}

resource apiOriginGroup 'Microsoft.Cdn/profiles/originGroups@2024-02-01' = {
  parent: profile
  name: 'api'
  properties: {
    loadBalancingSettings: { sampleSize: 4, successfulSamplesRequired: 3 }
    healthProbeSettings: {
      probePath: '/healthz'
      probeProtocol: 'Https'
      probeRequestType: 'GET'
      probeIntervalInSeconds: 30
    }
  }
}

resource apiOrigin 'Microsoft.Cdn/profiles/originGroups/origins@2024-02-01' = {
  parent: apiOriginGroup
  name: 'api-origin'
  properties: {
    hostName: apiOriginHostName
    originHostHeader: apiOriginHostName
    httpsPort: 443
    priority: 1
    weight: 1000
    enabledState: 'Enabled'
  }
}

resource spaRoute 'Microsoft.Cdn/profiles/afdEndpoints/routes@2024-02-01' = {
  parent: endpoint
  name: 'spa-route'
  properties: {
    originGroup: { id: webOriginGroup.id }
    supportedProtocols: ['Https']
    patternsToMatch: ['/*']
    forwardingProtocol: 'HttpsOnly'
    httpsRedirect: 'Enabled'
    linkToDefaultDomain: 'Enabled'
  }
  dependsOn: [webOrigin]
}

resource apiRoute 'Microsoft.Cdn/profiles/afdEndpoints/routes@2024-02-01' = {
  parent: endpoint
  name: 'api-route'
  properties: {
    originGroup: { id: apiOriginGroup.id }
    supportedProtocols: ['Https']
    patternsToMatch: ['/api/*']
    forwardingProtocol: 'HttpsOnly'
    httpsRedirect: 'Enabled'
    linkToDefaultDomain: 'Enabled'
  }
  dependsOn: [apiOrigin]
}

resource securityPolicy 'Microsoft.Cdn/profiles/securityPolicies@2024-02-01' = {
  parent: profile
  name: 'waf-association'
  properties: {
    parameters: {
      type: 'WebApplicationFirewall'
      wafPolicy: { id: wafPolicy.id }
      associations: [
        {
          domains: [{ id: endpoint.id }]
          patternsToMatch: ['/*']
        }
      ]
    }
  }
}

output endpointHostName string = endpoint.properties.hostName

// Azure Static Web Apps serves the React SPA as static assets behind Front Door
// (spec §5.3). Standard tier for the private-link origin + SLA.

param names object
param location string
param tags object

@allowed(['Free', 'Standard'])
param sku string = 'Standard'

resource web 'Microsoft.Web/staticSites@2023-12-01' = {
  name: names.staticWebApp
  location: location
  tags: tags
  sku: { name: sku, tier: sku }
  properties: {
    // CI builds and uploads assets; no repo integration from the platform side.
    allowConfigFileUpdates: true
    stagingEnvironmentPolicy: 'Enabled'
  }
}

output defaultHostName string = web.properties.defaultHostname
output name string = web.name

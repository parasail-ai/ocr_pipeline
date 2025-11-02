@description('Azure region for resources')
param location string = resourceGroup().location

@description('Azure App Service name')
param appServiceName string = 'parasail-ocr-pipeline'

@description('App Service plan name')
param appServicePlanName string = '${appServiceName}-plan'

@description('Azure Container Registry name (5-50 lowercase alphanumeric)')
param acrName string = 'parasailocr${uniqueString(resourceGroup().id)}'

@description('Unique storage account name (3-24 lowercase letters and numbers)')
param storageAccountName string

@description('App Service plan SKU')
param skuName string = 'B1'

@description('PostgreSQL connection string for the OCR database')
@secure()
param databaseConnection string

@description('Parasail API key used for OCR calls')
@secure()
param parasailApiKey string

@description('Default Parasail OCR model name')
param parasailDefaultModel string = 'parasail-matt-ocr-1-dots'

@description('Allowed CORS origins for the FastAPI service')
param allowedOrigins array = [
  'https://parasail-ocr-pipeline.azurewebsites.net'
]

var containerName = 'contracts'
var appSettings = [
  {
    name: 'APP_ENVIRONMENT'
    value: 'production'
  }
  {
    name: 'APP_DATABASE_URL'
    value: databaseConnection
  }
  {
    name: 'APP_PARASAIL_API_KEY'
    value: parasailApiKey
  }
  {
    name: 'APP_PARASAIL_DEFAULT_MODEL'
    value: parasailDefaultModel
  }
  {
    name: 'APP_AZURE_BLOB_CONTAINER'
    value: containerName
  }
  {
    name: 'APP_ALLOWED_ORIGINS'
    value: join(allowedOrigins, ',')
  }
  {
    name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
    value: '1'
  }
  {
    name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
    value: 'false'
  }
  {
    name: 'WEBSITES_PORT'
    value: '8000'
  }
]

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource storageContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/${containerName}'
  properties: {
    publicAccess: 'None'
  }
}

var storageKeys = storageAccount.listKeys()
var storageConnectionString = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageKeys.keys[0].value};EndpointSuffix=${environment().suffixes.storage}'

resource appServicePlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: skuName
    tier: skuName == 'B1' ? 'Basic' : 'Standard'
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

resource webApp 'Microsoft.Web/sites@2022-09-01' = {
  name: appServiceName
  location: location
  kind: 'app,linux,container'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    httpsOnly: true
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: 'DOCKER|${acr.properties.loginServer}/parasail-ocr:latest'
      appSettings: concat(appSettings, [
        {
          name: 'APP_AZURE_STORAGE_CONNECTION_STRING'
          value: storageConnectionString
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_URL'
          value: 'https://${acr.properties.loginServer}'
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_USERNAME'
          value: acr.listCredentials().username
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_PASSWORD'
          value: acr.listCredentials().passwords[0].value
        }
      ])
      alwaysOn: true
      ftpsState: 'Disabled'
    }
  }
}

output appServiceEndpoint string = webApp.properties.defaultHostName
output storageAccountId string = storageAccount.id
output blobContainerName string = containerName

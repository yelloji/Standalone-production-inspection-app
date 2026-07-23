import { contextBridge } from 'electron'

contextBridge.exposeInMainWorld('productionInspection', {
  platform: process.platform,
})

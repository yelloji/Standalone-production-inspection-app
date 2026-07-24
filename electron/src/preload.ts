import { contextBridge, ipcRenderer } from 'electron'

import {
  BACKEND_REQUEST_CHANNEL,
  type BackendRequest,
  type BackendResponse,
  type DesktopBridge,
} from './contracts'

const bridge: DesktopBridge = Object.freeze({
  platform: process.platform,
  isPackaged: !process.defaultApp,
  backend: Object.freeze({
    request: (request: BackendRequest) =>
      ipcRenderer.invoke(BACKEND_REQUEST_CHANNEL, request) as Promise<BackendResponse>,
  }),
})

contextBridge.exposeInMainWorld('productionInspection', bridge)

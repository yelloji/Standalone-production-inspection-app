import { contextBridge, ipcRenderer } from 'electron'

import type { BackendRequest, BackendResponse, DesktopBridge } from './contracts'

// Sandboxed Electron preloads may not require local modules. Keep channel
// values self-contained here while sharing only erased TypeScript types.
const BACKEND_REQUEST_CHANNEL = 'inspection:backend-request'
const MODEL_BUNDLE_SELECT_CHANNEL = 'inspection:select-model-bundle'
const ACQUISITION_FOLDER_SELECT_CHANNEL = 'inspection:select-acquisition-folder'
const CENTER_REFERENCE_SELECT_CHANNEL = 'inspection:select-center-reference'

const bridge: DesktopBridge = Object.freeze({
  platform: process.platform,
  isPackaged: !process.defaultApp,
  backend: Object.freeze({
    request: (request: BackendRequest) =>
      ipcRenderer.invoke(BACKEND_REQUEST_CHANNEL, request) as Promise<BackendResponse>,
  }),
  models: Object.freeze({
    selectBundle: () =>
      ipcRenderer.invoke(MODEL_BUNDLE_SELECT_CHANNEL) as Promise<string | null>,
  }),
  acquisitions: Object.freeze({
    selectFolder: () =>
      ipcRenderer.invoke(ACQUISITION_FOLDER_SELECT_CHANNEL) as Promise<string | null>,
  }),
  centerReferences: Object.freeze({
    selectImage: (side: 'upper' | 'lower') =>
      ipcRenderer.invoke(
        CENTER_REFERENCE_SELECT_CHANNEL,
        side,
      ) as Promise<string | null>,
  }),
})

contextBridge.exposeInMainWorld('productionInspection', bridge)

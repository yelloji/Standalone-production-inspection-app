import path from 'node:path'

import { app, BrowserWindow, ipcMain, session, shell } from 'electron'

import { sendBackendRequest } from './backend-bridge'
import { BACKEND_REQUEST_CHANNEL } from './contracts'

const DEVELOPMENT_RENDERER_URL = 'http://127.0.0.1:5173'
const EXTERNAL_PROTOCOLS = new Set(['https:'])

let mainWindow: BrowserWindow | null = null

function isTrustedApplicationUrl(value: string): boolean {
  try {
    const url = new URL(value)
    if (!app.isPackaged) {
      return url.origin === DEVELOPMENT_RENDERER_URL
    }
    return url.protocol === 'file:'
  } catch {
    return false
  }
}

function openExternalUrl(value: string): void {
  try {
    const url = new URL(value)
    if (EXTERNAL_PROTOCOLS.has(url.protocol)) {
      void shell.openExternal(url.toString())
    }
  } catch {
    // Invalid external URLs are intentionally ignored.
  }
}

function createWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 680,
    show: false,
    backgroundColor: '#081116',
    title: 'Standalone Production Inspection',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      devTools: !app.isPackaged,
    },
  })

  window.once('ready-to-show', () => window.show())
  window.on('closed', () => {
    if (mainWindow === window) {
      mainWindow = null
    }
  })

  window.webContents.setWindowOpenHandler(({ url }) => {
    openExternalUrl(url)
    return { action: 'deny' }
  })
  window.webContents.on('will-navigate', (event, url) => {
    if (!isTrustedApplicationUrl(url)) {
      event.preventDefault()
    }
  })
  window.webContents.on('will-attach-webview', (event) => event.preventDefault())

  if (app.isPackaged) {
    void window.loadFile(path.join(__dirname, '../../frontend/dist/index.html'))
  } else {
    void window.loadURL(DEVELOPMENT_RENDERER_URL)
  }
  return window
}

const ownsSingleInstance = app.requestSingleInstanceLock()
if (!ownsSingleInstance) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) {
        mainWindow.restore()
      }
      mainWindow.focus()
    }
  })

  app.whenReady().then(() => {
    session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => {
      callback(false)
    })
    ipcMain.handle(BACKEND_REQUEST_CHANNEL, (_event, request: unknown) =>
      sendBackendRequest(request),
    )
    mainWindow = createWindow()

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        mainWindow = createWindow()
      }
    })
  })
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

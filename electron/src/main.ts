import path from 'node:path'

import { app, BrowserWindow, shell } from 'electron'

const DEVELOPMENT_RENDERER_URL = 'http://127.0.0.1:5173'

function isTrustedApplicationUrl(value: string): boolean {
  if (!app.isPackaged) {
    return value.startsWith(DEVELOPMENT_RENDERER_URL)
  }
  return value.startsWith('file:')
}

function createWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    show: false,
    backgroundColor: '#0b0f12',
    title: 'Standalone Production Inspection',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  })

  window.once('ready-to-show', () => {
    window.show()
  })

  window.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://')) {
      void shell.openExternal(url)
    }
    return { action: 'deny' }
  })

  window.webContents.on('will-navigate', (event, url) => {
    if (!isTrustedApplicationUrl(url)) {
      event.preventDefault()
    }
  })

  if (app.isPackaged) {
    void window.loadFile(path.join(__dirname, '../../frontend/dist/index.html'))
  } else {
    void window.loadURL(DEVELOPMENT_RENDERER_URL)
  }

  return window
}

app.whenReady().then(() => {
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

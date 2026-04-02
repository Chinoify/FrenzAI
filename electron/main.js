const { app, BrowserWindow, ipcMain, dialog } = require('electron')
const path = require('path')
const { spawn, execSync } = require('child_process')

let mainWindow = null
let splashWindow = null
let pythonProcess = null
const BACKEND_PORT = 8111
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`

// --- Python Backend Management ---

function findPython() {
  // Try common Python commands
  for (const cmd of ['python', 'python3', 'py']) {
    try {
      const version = execSync(`${cmd} --version 2>&1`, { encoding: 'utf-8' }).trim()
      if (version.includes('Python 3')) {
        console.log(`[Python] Found: ${cmd} → ${version}`)
        return cmd
      }
    } catch {
      // Try next
    }
  }
  return null
}

function startBackend() {
  const backendDir = path.join(__dirname, '..', 'backend')
  const pythonCmd = findPython()

  if (!pythonCmd) {
    dialog.showErrorBox(
      'Python Not Found',
      'VoiceForge Studio requires Python 3.11+.\n\nPlease install Python from https://www.python.org/downloads/\n\nMake sure to check "Add Python to PATH" during installation.'
    )
    app.quit()
    return
  }

  console.log(`[Backend] Starting with ${pythonCmd} in ${backendDir}`)

  pythonProcess = spawn(pythonCmd, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)], {
    cwd: backendDir,
    stdio: ['pipe', 'pipe', 'pipe'],
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
    windowsHide: true,
  })

  pythonProcess.stdout.on('data', (data) => {
    const msg = data.toString().trim()
    console.log(`[Backend] ${msg}`)
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.webContents.executeJavaScript(
        `document.getElementById('status').innerText = "Starting engine..."`
      ).catch(() => {})
    }
  })

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[Backend] ${data.toString().trim()}`)
  })

  pythonProcess.on('close', (code) => {
    console.log(`[Backend] Process exited with code ${code}`)
    pythonProcess = null
  })

  pythonProcess.on('error', (err) => {
    console.error(`[Backend] Failed to start: ${err.message}`)
    pythonProcess = null
  })
}

function stopBackend() {
  if (pythonProcess) {
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', String(pythonProcess.pid), '/f', '/t'], { windowsHide: true })
    } else {
      pythonProcess.kill('SIGTERM')
    }
    setTimeout(() => {
      if (pythonProcess) {
        try { pythonProcess.kill('SIGKILL') } catch {}
      }
    }, 5000)
  }
}

async function waitForBackend(maxRetries = 45, intervalMs = 1000) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await fetch(`${BACKEND_URL}/api/health`)
      if (response.ok) {
        console.log('[Backend] Ready!')
        return true
      }
    } catch {
      // Not ready yet
    }
    if (splashWindow && !splashWindow.isDestroyed()) {
      const dots = '.'.repeat((i % 3) + 1)
      splashWindow.webContents.executeJavaScript(
        `document.getElementById('status').innerText = "Starting backend${dots}"`
      ).catch(() => {})
    }
    await new Promise((r) => setTimeout(r, intervalMs))
  }
  console.error('[Backend] Failed to start within timeout')
  return false
}

// --- Splash Screen ---

function createSplash() {
  splashWindow = new BrowserWindow({
    width: 420,
    height: 300,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    webPreferences: {
      contextIsolation: true,
    },
  })

  const splashHTML = `data:text/html;charset=utf-8,${encodeURIComponent(`
<!DOCTYPE html>
<html>
<head>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: #09090b;
    color: #fafafa;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100vh;
    border-radius: 16px;
    border: 1px solid #27272a;
    overflow: hidden;
    -webkit-app-region: drag;
  }
  .container { text-align: center; padding: 40px; }
  .icon {
    width: 64px; height: 64px;
    background: linear-gradient(135deg, #8b5cf6, #7c3aed);
    border-radius: 16px;
    margin: 0 auto 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 28px;
  }
  h1 { font-size: 22px; font-weight: 600; margin-bottom: 6px; }
  .sub { color: #71717a; font-size: 13px; margin-bottom: 30px; }
  .spinner {
    width: 28px; height: 28px;
    border: 3px solid #27272a;
    border-top: 3px solid #8b5cf6;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto 14px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  #status { color: #a1a1aa; font-size: 12px; }
</style>
</head>
<body>
  <div class="container">
    <div class="icon">🎙️</div>
    <h1>VoiceForge Studio</h1>
    <p class="sub">Offline Voice Cloning & TTS</p>
    <div class="spinner"></div>
    <p id="status">Starting...</p>
  </div>
</body>
</html>
  `)}`

  splashWindow.loadURL(splashHTML)
}

// --- Main Window ---

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#09090b',
    title: 'VoiceForge Studio',
    icon: path.join(__dirname, '..', 'resources', 'icons', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    show: false,
  })

  // Always load the built frontend files
  const indexPath = path.join(__dirname, '..', 'frontend', 'dist', 'index.html')
  mainWindow.loadFile(indexPath)

  mainWindow.once('ready-to-show', () => {
    // Close splash and show main window
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.close()
      splashWindow = null
    }
    mainWindow.show()
    mainWindow.focus()
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// --- App Lifecycle ---

app.whenReady().then(async () => {
  // Show splash screen
  createSplash()

  // Start backend
  startBackend()

  // Wait for backend to be ready
  const backendReady = await waitForBackend()

  if (!backendReady) {
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.close()
    }
    dialog.showErrorBox(
      'Backend Error',
      'Failed to start the Python backend.\n\nMake sure:\n1. Python 3.11+ is installed\n2. Run: pip install -r backend/requirements.txt\n3. No other app is using port 8111'
    )
    app.quit()
    return
  }

  // Backend ready — create main window
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  stopBackend()
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  stopBackend()
})

// --- IPC Handlers ---

ipcMain.handle('dialog:openFile', async (_, options) => {
  const result = await dialog.showOpenDialog(mainWindow, options)
  return result
})

ipcMain.handle('dialog:saveFile', async (_, options) => {
  const result = await dialog.showSaveDialog(mainWindow, options)
  return result
})

ipcMain.handle('app:getVersion', () => {
  return app.getVersion()
})

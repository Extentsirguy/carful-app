/**
 * CARFul - Electron Main Process
 *
 * This is the main entry point for the Electron application.
 * It manages the application lifecycle, window creation, and IPC communication.
 *
 * Security: nodeIntegration is disabled, contextIsolation is enabled.
 * All renderer-main communication flows through the preload script.
 */

// Handle Squirrel.Windows installer events FIRST — before anything else
const { handleSquirrelEvent } = require('./squirrel-handler');
if (handleSquirrelEvent()) {
    // Squirrel event handled, app will quit — don't initialize anything else
    return;
}

const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const Store = require('electron-store');
const { createApplicationMenu } = require('./menu');
const { PythonBridge } = require('./python-bridge');
const { initializeAutoUpdater, checkForUpdatesOnStart } = require('./updater');

// Initialize settings store
const store = new Store({
    name: 'carful-settings',
    defaults: {
        rcasp: {
            name: '',
            tin: '',
            country: 'US',
            city: '',
            street: '',
        },
        export: {
            sendingCountry: 'US',
            receivingCountry: 'GB',
            reportingYear: new Date().getFullYear(),
            messageType: 'CARF1',
        },
        advanced: {
            validationStrictness: 'strict',
            autoUpdate: true,
            debugMode: false,
        },
    },
});

// Initialize license store
const licenseStore = new Store({
    name: 'carful-license',
    defaults: {},
});

// Keep a global reference of the window object to prevent garbage collection
let mainWindow = null;
let pythonBridge = null;

// Default window dimensions
const DEFAULT_WIDTH = 1200;
const DEFAULT_HEIGHT = 800;
const MIN_WIDTH = 800;
const MIN_HEIGHT = 600;

/**
 * Create the main application window with secure defaults.
 */
function createWindow() {
    mainWindow = new BrowserWindow({
        width: DEFAULT_WIDTH,
        height: DEFAULT_HEIGHT,
        minWidth: MIN_WIDTH,
        minHeight: MIN_HEIGHT,
        title: 'CARFul - CARF Compliance Tool',
        icon: path.join(__dirname, '../../resources/icon.png'),
        webPreferences: {
            // Security: Disable node integration in renderer
            nodeIntegration: false,
            // Security: Enable context isolation
            contextIsolation: true,
            // Security: Enable sandbox (disabled in dev for Vite compatibility)
            sandbox: false,
            // Preload script provides safe IPC API
            preload: path.join(__dirname, 'preload.js'),
            // Content Security Policy
            webSecurity: true,
        },
        // Show window when ready to prevent white flash
        show: false,
        backgroundColor: '#f8fafc', // Tailwind slate-50
    });

    // Load the renderer — use Vite dev server in development, built files in production
    const isDev = !app.isPackaged;
    if (isDev) {
        mainWindow.loadURL('http://localhost:5173');
    } else {
        mainWindow.loadFile(path.join(__dirname, '../../dist/renderer/index.html'));
    }

    // Show window when ready
    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
    });

    // Handle window close
    mainWindow.on('closed', () => {
        mainWindow = null;
    });

    // Open DevTools in development
    if (isDev) {
        mainWindow.webContents.openDevTools();
    }

    return mainWindow;
}

/**
 * Initialize the Python backend bridge.
 */
function initializePythonBridge() {
    pythonBridge = new PythonBridge();

    // Handle RPC requests from renderer
    ipcMain.handle('rpc:invoke', async (event, method, params) => {
        try {
            return await pythonBridge.invoke(method, params);
        } catch (error) {
            console.error(`RPC error for ${method}:`, error);
            throw error;
        }
    });
}

/**
 * Set up IPC handlers for file dialogs.
 */
function setupIPCHandlers() {
    // Open file dialog for CSV import
    ipcMain.handle('dialog:openCSV', async () => {
        const result = await dialog.showOpenDialog(mainWindow, {
            title: 'Select CSV File to Import',
            filters: [
                { name: 'CSV Files', extensions: ['csv'] },
                { name: 'All Files', extensions: ['*'] },
            ],
            properties: ['openFile'],
        });
        return result.canceled ? null : result.filePaths[0];
    });

    // Save file dialog for XML export
    ipcMain.handle('dialog:saveXML', async (event, defaultName) => {
        const result = await dialog.showSaveDialog(mainWindow, {
            title: 'Export CARF XML',
            defaultPath: defaultName || 'carf_export.xml',
            filters: [
                { name: 'XML Files', extensions: ['xml'] },
            ],
        });
        return result.canceled ? null : result.filePath;
    });

    // Save file dialog for PDF report
    ipcMain.handle('dialog:savePDF', async (event, defaultName) => {
        const result = await dialog.showSaveDialog(mainWindow, {
            title: 'Save Health Check Report',
            defaultPath: defaultName || 'health_check_report.pdf',
            filters: [
                { name: 'PDF Files', extensions: ['pdf'] },
            ],
        });
        return result.canceled ? null : result.filePath;
    });

    // Get app version
    ipcMain.handle('app:version', () => {
        return app.getVersion();
    });

    // Get app paths
    ipcMain.handle('app:paths', () => {
        return {
            userData: app.getPath('userData'),
            temp: app.getPath('temp'),
            documents: app.getPath('documents'),
        };
    });

    // Settings handlers using electron-store
    ipcMain.handle('settings:get', (event, key) => {
        return store.get(key);
    });

    ipcMain.handle('settings:set', (event, key, value) => {
        store.set(key, value);
    });

    ipcMain.handle('settings:getAll', () => {
        return store.store;
    });

    ipcMain.handle('settings:delete', (event, key) => {
        store.delete(key);
    });

    ipcMain.handle('settings:reset', () => {
        store.clear();
    });

    // Show file in system file manager
    ipcMain.handle('shell:showItemInFolder', (event, filePath) => {
        shell.showItemInFolder(filePath);
    });

    // License handlers
    ipcMain.handle('license:getMachineId', () => {
        const hostname = os.hostname();
        const platform = os.platform();
        const arch = os.arch();
        const cpuModel = os.cpus()[0]?.model || 'unknown';
        const combined = `${hostname}${platform}${arch}${cpuModel}`;
        const hash = crypto.createHash('sha256').update(combined).digest('hex');
        return hash.substring(0, 16);
    });

    ipcMain.handle('license:get', () => {
        return licenseStore.store || null;
    });

    ipcMain.handle('license:set', (event, data) => {
        licenseStore.set(data);
    });

    ipcMain.handle('license:clear', () => {
        licenseStore.clear();
    });
}

// App lifecycle events
app.whenReady().then(() => {
    // Create application menu
    createApplicationMenu();

    // Initialize Python bridge
    initializePythonBridge();

    // Set up IPC handlers
    setupIPCHandlers();

    // Create main window
    createWindow();

    // Initialize auto-updater
    initializeAutoUpdater(mainWindow);

    // Check for updates on start (if enabled)
    if (store.get('advanced.autoUpdate', true)) {
        checkForUpdatesOnStart(mainWindow);
    }

    // macOS: Re-create window when dock icon clicked
    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

// Quit when all windows are closed (except on macOS)
app.on('window-all-closed', () => {
    // Clean up Python bridge
    if (pythonBridge) {
        pythonBridge.shutdown();
    }

    if (process.platform !== 'darwin') {
        app.quit();
    }
});

// Security: Prevent new window creation
app.on('web-contents-created', (event, contents) => {
    contents.on('new-window', (event) => {
        event.preventDefault();
    });

    // Prevent navigation to external URLs (allow localhost in dev mode)
    contents.on('will-navigate', (event, url) => {
        const parsedUrl = new URL(url);
        const isDev = !app.isPackaged;
        const isLocalhost = parsedUrl.hostname === 'localhost' || parsedUrl.hostname === '127.0.0.1';
        if (parsedUrl.protocol === 'file:') return;
        if (isDev && isLocalhost) return;
        event.preventDefault();
    });
});

module.exports = { mainWindow, pythonBridge };

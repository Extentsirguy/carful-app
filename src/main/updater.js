/**
 * CARFul - Auto-Update Module
 *
 * Handles automatic updates using electron-updater with GitHub Releases.
 * Features:
 * - Check for updates on app launch
 * - Background download with progress
 * - Install on quit/restart
 * - Schema version checking
 */

const { autoUpdater } = require('electron-updater');
const { ipcMain, BrowserWindow } = require('electron');
const path = require('path');
const fs = require('fs');
const https = require('https');

// Configure logging
autoUpdater.logger = require('electron-log');
autoUpdater.logger.transports.file.level = 'info';

// Update configuration
autoUpdater.autoDownload = false; // Don't auto-download, let user decide
autoUpdater.autoInstallOnAppQuit = true;

// Schema version URL (for checking XSD updates)
const SCHEMA_VERSION_URL = 'https://raw.githubusercontent.com/carful/carful/main/schemas/version.json';

/**
 * Initialize the auto-updater with event handlers.
 * @param {BrowserWindow} mainWindow - The main application window
 */
function initializeAutoUpdater(mainWindow) {
    // Check for updates
    autoUpdater.on('checking-for-update', () => {
        sendStatusToWindow(mainWindow, 'checking', 'Checking for updates...');
    });

    // Update available
    autoUpdater.on('update-available', (info) => {
        sendStatusToWindow(mainWindow, 'available', {
            version: info.version,
            releaseDate: info.releaseDate,
            releaseNotes: info.releaseNotes,
        });
    });

    // No update available
    autoUpdater.on('update-not-available', (info) => {
        sendStatusToWindow(mainWindow, 'not-available', {
            version: info.version,
        });
    });

    // Download progress
    autoUpdater.on('download-progress', (progressObj) => {
        sendStatusToWindow(mainWindow, 'progress', {
            percent: progressObj.percent,
            bytesPerSecond: progressObj.bytesPerSecond,
            transferred: progressObj.transferred,
            total: progressObj.total,
        });
    });

    // Update downloaded
    autoUpdater.on('update-downloaded', (info) => {
        sendStatusToWindow(mainWindow, 'downloaded', {
            version: info.version,
            releaseNotes: info.releaseNotes,
        });
    });

    // Error handling
    autoUpdater.on('error', (err) => {
        sendStatusToWindow(mainWindow, 'error', {
            message: err.message,
        });
    });

    // Set up IPC handlers
    setupIPCHandlers(mainWindow);
}

/**
 * Send update status to renderer process.
 */
function sendStatusToWindow(mainWindow, status, data) {
    if (mainWindow && mainWindow.webContents) {
        mainWindow.webContents.send('update:status', { status, data });
    }
}

/**
 * Set up IPC handlers for update-related actions.
 */
function setupIPCHandlers(mainWindow) {
    // Check for updates manually
    ipcMain.handle('update:check', async () => {
        try {
            const result = await autoUpdater.checkForUpdates();
            return {
                updateAvailable: result?.updateInfo?.version !== undefined,
                version: result?.updateInfo?.version,
            };
        } catch (error) {
            return { error: error.message };
        }
    });

    // Download update
    ipcMain.handle('update:download', async () => {
        try {
            await autoUpdater.downloadUpdate();
            return { success: true };
        } catch (error) {
            return { error: error.message };
        }
    });

    // Install update and restart
    ipcMain.handle('update:install', () => {
        autoUpdater.quitAndInstall(false, true);
    });

    // Check schema version
    ipcMain.handle('update:checkSchema', async () => {
        return await checkSchemaVersion();
    });

    // Get current app version
    ipcMain.handle('update:currentVersion', () => {
        return {
            app: require('../../package.json').version,
            electron: process.versions.electron,
            node: process.versions.node,
        };
    });
}

/**
 * Check for schema updates (XSD files).
 */
async function checkSchemaVersion() {
    return new Promise((resolve) => {
        // Try to get local schema version
        let localVersion = '1.0.0';
        try {
            const versionPath = path.join(__dirname, '../../schemas/version.json');
            if (fs.existsSync(versionPath)) {
                const versionData = JSON.parse(fs.readFileSync(versionPath, 'utf8'));
                localVersion = versionData.version;
            }
        } catch (error) {
            console.error('Error reading local schema version:', error);
        }

        // Try to get remote schema version
        https.get(SCHEMA_VERSION_URL, { timeout: 5000 }, (res) => {
            let data = '';
            res.on('data', (chunk) => { data += chunk; });
            res.on('end', () => {
                try {
                    const remoteVersion = JSON.parse(data).version;
                    resolve({
                        local: localVersion,
                        remote: remoteVersion,
                        updateAvailable: remoteVersion !== localVersion,
                    });
                } catch (error) {
                    resolve({
                        local: localVersion,
                        remote: null,
                        error: 'Failed to parse remote schema version',
                    });
                }
            });
        }).on('error', (error) => {
            resolve({
                local: localVersion,
                remote: null,
                error: error.message,
            });
        });
    });
}

/**
 * Check for updates on app start.
 */
async function checkForUpdatesOnStart(mainWindow) {
    // Wait a bit before checking to allow app to fully load
    setTimeout(async () => {
        try {
            await autoUpdater.checkForUpdates();
        } catch (error) {
            console.error('Auto-update check failed:', error);
        }
    }, 3000);
}

module.exports = {
    initializeAutoUpdater,
    checkForUpdatesOnStart,
    checkSchemaVersion,
};

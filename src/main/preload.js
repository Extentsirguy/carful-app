/**
 * CARFul - Preload Script
 *
 * This script provides a secure bridge between the renderer process
 * and the main process using contextBridge.
 *
 * Security: Only exposes specific, whitelisted APIs to the renderer.
 * The renderer has no direct access to Node.js or Electron APIs.
 */

const { contextBridge, ipcRenderer } = require('electron');

/**
 * Expose a safe API to the renderer process.
 * This is the ONLY way the renderer can communicate with Node.js.
 */
contextBridge.exposeInMainWorld('carful', {
    // ============================================================
    // RPC Methods - Communication with Python Backend
    // ============================================================

    /**
     * Invoke an RPC method on the Python backend.
     * @param {string} method - The RPC method name
     * @param {object} params - Method parameters
     * @returns {Promise<any>} - The RPC response
     */
    rpc: {
        invoke: (method, params = {}) => {
            return ipcRenderer.invoke('rpc:invoke', method, params);
        },

        // Convenience methods for common operations
        stats: (dbPath) => ipcRenderer.invoke('rpc:invoke', 'db.stats', { db_path: dbPath }),
        importCSV: (csvPath, dbPath) => ipcRenderer.invoke('rpc:invoke', 'csv.import', { csv_path: csvPath, db_path: dbPath }),
        validateTINs: (dbPath) => ipcRenderer.invoke('rpc:invoke', 'tin.validate', { db_path: dbPath }),
        exportXML: (dbPath, output, config) => ipcRenderer.invoke('rpc:invoke', 'xml.export', { db_path: dbPath, output, config }),
        healthCheck: (csvPath) => ipcRenderer.invoke('rpc:invoke', 'health.check', { csv_path: csvPath }),
        generatePDF: (checkResult, output) => ipcRenderer.invoke('rpc:invoke', 'report.pdf', { check_result: checkResult, output }),
    },

    // ============================================================
    // File Dialogs
    // ============================================================

    dialog: {
        /**
         * Open a file dialog to select a CSV file.
         * @returns {Promise<string|null>} - Selected file path or null if canceled
         */
        openCSV: () => ipcRenderer.invoke('dialog:openCSV'),

        /**
         * Open a save dialog for XML export.
         * @param {string} defaultName - Default filename
         * @returns {Promise<string|null>} - Selected file path or null if canceled
         */
        saveXML: (defaultName) => ipcRenderer.invoke('dialog:saveXML', defaultName),

        /**
         * Open a save dialog for PDF report.
         * @param {string} defaultName - Default filename
         * @returns {Promise<string|null>} - Selected file path or null if canceled
         */
        savePDF: (defaultName) => ipcRenderer.invoke('dialog:savePDF', defaultName),
    },

    // ============================================================
    // Application Info
    // ============================================================

    app: {
        /**
         * Get the application version.
         * @returns {Promise<string>} - Version string
         */
        getVersion: () => ipcRenderer.invoke('app:version'),

        /**
         * Get application paths.
         * @returns {Promise<{userData: string, temp: string, documents: string}>}
         */
        getPaths: () => ipcRenderer.invoke('app:paths'),
    },

    // ============================================================
    // Event Listeners
    // ============================================================

    events: {
        /**
         * Listen for progress updates from long-running operations.
         * @param {function} callback - Progress callback (percent, message)
         * @returns {function} - Cleanup function to remove listener
         */
        onProgress: (callback) => {
            const handler = (event, data) => callback(data.percent, data.message);
            ipcRenderer.on('progress:update', handler);
            return () => ipcRenderer.removeListener('progress:update', handler);
        },

        /**
         * Listen for validation errors.
         * @param {function} callback - Error callback (errors)
         * @returns {function} - Cleanup function to remove listener
         */
        onValidationError: (callback) => {
            const handler = (event, errors) => callback(errors);
            ipcRenderer.on('validation:errors', handler);
            return () => ipcRenderer.removeListener('validation:errors', handler);
        },

        /**
         * Listen for update availability.
         * @param {function} callback - Update callback (version, releaseNotes)
         * @returns {function} - Cleanup function to remove listener
         */
        onUpdateAvailable: (callback) => {
            const handler = (event, data) => callback(data.version, data.releaseNotes);
            ipcRenderer.on('update:available', handler);
            return () => ipcRenderer.removeListener('update:available', handler);
        },
    },

    // ============================================================
    // Settings Storage
    // ============================================================

    settings: {
        /**
         * Get a setting value.
         * @param {string} key - Setting key
         * @returns {Promise<any>} - Setting value
         */
        get: (key) => ipcRenderer.invoke('settings:get', key),

        /**
         * Set a setting value.
         * @param {string} key - Setting key
         * @param {any} value - Setting value
         * @returns {Promise<void>}
         */
        set: (key, value) => ipcRenderer.invoke('settings:set', key, value),

        /**
         * Get all settings.
         * @returns {Promise<object>} - All settings
         */
        getAll: () => ipcRenderer.invoke('settings:getAll'),
    },

    // ============================================================
    // License Management
    // ============================================================

    license: {
        /**
         * Get the machine ID for this device.
         * @returns {Promise<string>} - Deterministic machine ID hash
         */
        getMachineId: () => ipcRenderer.invoke('license:getMachineId'),

        /**
         * Get stored license data.
         * @returns {Promise<object|null>} - License data or null
         */
        get: () => ipcRenderer.invoke('license:get'),

        /**
         * Store license data.
         * @param {object} data - License data to store
         * @returns {Promise<void>}
         */
        set: (data) => ipcRenderer.invoke('license:set', data),

        /**
         * Clear stored license data.
         * @returns {Promise<void>}
         */
        clear: () => ipcRenderer.invoke('license:clear'),
    },

    // ============================================================
    // Shell Operations
    // ============================================================

    shell: {
        showItemInFolder: (filePath) => ipcRenderer.invoke('shell:showItemInFolder', filePath),
    },
});

// Log that preload script has loaded
console.log('CARFul preload script loaded');

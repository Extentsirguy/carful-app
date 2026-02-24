/**
 * CARFul - Application Menu
 *
 * Defines the native application menu with File, Edit, View, and Help menus.
 */

const { app, Menu, shell, BrowserWindow } = require('electron');

/**
 * Create and set the application menu.
 */
function createApplicationMenu() {
    const isMac = process.platform === 'darwin';

    const template = [
        // App menu (macOS only)
        ...(isMac ? [{
            label: app.name,
            submenu: [
                { role: 'about' },
                { type: 'separator' },
                {
                    label: 'Preferences...',
                    accelerator: 'CmdOrCtrl+,',
                    click: () => {
                        const win = BrowserWindow.getFocusedWindow();
                        if (win) {
                            win.webContents.send('menu:preferences');
                        }
                    },
                },
                { type: 'separator' },
                { role: 'services' },
                { type: 'separator' },
                { role: 'hide' },
                { role: 'hideOthers' },
                { role: 'unhide' },
                { type: 'separator' },
                { role: 'quit' },
            ],
        }] : []),

        // File menu
        {
            label: 'File',
            submenu: [
                {
                    label: 'Import CSV...',
                    accelerator: 'CmdOrCtrl+O',
                    click: () => {
                        const win = BrowserWindow.getFocusedWindow();
                        if (win) {
                            win.webContents.send('menu:importCSV');
                        }
                    },
                },
                { type: 'separator' },
                {
                    label: 'Export XML...',
                    accelerator: 'CmdOrCtrl+E',
                    click: () => {
                        const win = BrowserWindow.getFocusedWindow();
                        if (win) {
                            win.webContents.send('menu:exportXML');
                        }
                    },
                },
                {
                    label: 'Generate Health Check Report...',
                    accelerator: 'CmdOrCtrl+Shift+H',
                    click: () => {
                        const win = BrowserWindow.getFocusedWindow();
                        if (win) {
                            win.webContents.send('menu:healthCheck');
                        }
                    },
                },
                { type: 'separator' },
                ...(isMac ? [] : [
                    {
                        label: 'Settings...',
                        accelerator: 'CmdOrCtrl+,',
                        click: () => {
                            const win = BrowserWindow.getFocusedWindow();
                            if (win) {
                                win.webContents.send('menu:preferences');
                            }
                        },
                    },
                    { type: 'separator' },
                ]),
                isMac ? { role: 'close' } : { role: 'quit' },
            ],
        },

        // Edit menu
        {
            label: 'Edit',
            submenu: [
                { role: 'undo' },
                { role: 'redo' },
                { type: 'separator' },
                { role: 'cut' },
                { role: 'copy' },
                { role: 'paste' },
                ...(isMac ? [
                    { role: 'pasteAndMatchStyle' },
                    { role: 'delete' },
                    { role: 'selectAll' },
                ] : [
                    { role: 'delete' },
                    { type: 'separator' },
                    { role: 'selectAll' },
                ]),
            ],
        },

        // View menu
        {
            label: 'View',
            submenu: [
                {
                    label: 'Dashboard',
                    accelerator: 'CmdOrCtrl+1',
                    click: () => {
                        const win = BrowserWindow.getFocusedWindow();
                        if (win) {
                            win.webContents.send('menu:navigate', 'dashboard');
                        }
                    },
                },
                {
                    label: 'Import',
                    accelerator: 'CmdOrCtrl+2',
                    click: () => {
                        const win = BrowserWindow.getFocusedWindow();
                        if (win) {
                            win.webContents.send('menu:navigate', 'import');
                        }
                    },
                },
                {
                    label: 'Validation Results',
                    accelerator: 'CmdOrCtrl+3',
                    click: () => {
                        const win = BrowserWindow.getFocusedWindow();
                        if (win) {
                            win.webContents.send('menu:navigate', 'validation');
                        }
                    },
                },
                {
                    label: 'Export',
                    accelerator: 'CmdOrCtrl+4',
                    click: () => {
                        const win = BrowserWindow.getFocusedWindow();
                        if (win) {
                            win.webContents.send('menu:navigate', 'export');
                        }
                    },
                },
                { type: 'separator' },
                { role: 'reload' },
                { role: 'forceReload' },
                { role: 'toggleDevTools' },
                { type: 'separator' },
                { role: 'resetZoom' },
                { role: 'zoomIn' },
                { role: 'zoomOut' },
                { type: 'separator' },
                { role: 'togglefullscreen' },
            ],
        },

        // Window menu
        {
            label: 'Window',
            submenu: [
                { role: 'minimize' },
                { role: 'zoom' },
                ...(isMac ? [
                    { type: 'separator' },
                    { role: 'front' },
                    { type: 'separator' },
                    { role: 'window' },
                ] : [
                    { role: 'close' },
                ]),
            ],
        },

        // Help menu
        {
            role: 'help',
            submenu: [
                {
                    label: 'CARFul Documentation',
                    click: async () => {
                        await shell.openExternal('https://docs.carful.com');
                    },
                },
                {
                    label: 'OECD CARF Specification',
                    click: async () => {
                        await shell.openExternal('https://www.oecd.org/tax/exchange-of-tax-information/crypto-asset-reporting-framework-and-amendments-to-the-common-reporting-standard.htm');
                    },
                },
                { type: 'separator' },
                {
                    label: 'Check for Updates...',
                    click: () => {
                        const win = BrowserWindow.getFocusedWindow();
                        if (win) {
                            win.webContents.send('menu:checkUpdates');
                        }
                    },
                },
                { type: 'separator' },
                {
                    label: 'Report Issue...',
                    click: async () => {
                        await shell.openExternal('https://github.com/carful/carful/issues');
                    },
                },
                ...(isMac ? [] : [
                    { type: 'separator' },
                    {
                        label: 'About CARFul',
                        click: () => {
                            const win = BrowserWindow.getFocusedWindow();
                            if (win) {
                                win.webContents.send('menu:about');
                            }
                        },
                    },
                ]),
            ],
        },
    ];

    const menu = Menu.buildFromTemplate(template);
    Menu.setApplicationMenu(menu);
}

module.exports = { createApplicationMenu };

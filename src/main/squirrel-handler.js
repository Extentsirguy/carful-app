/**
 * CARFul - Squirrel.Windows Event Handler
 *
 * Handles Windows installer events:
 * - --squirrel-install: First install — create shortcuts
 * - --squirrel-updated: After update — update shortcuts
 * - --squirrel-uninstall: Uninstall — remove shortcuts
 * - --squirrel-obsolete: Old version being replaced
 *
 * Must be called at the very start of app initialization.
 * Returns true if a Squirrel event was handled (app should quit).
 */

const { app } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

function handleSquirrelEvent() {
    if (process.platform !== 'win32') {
        return false;
    }

    const squirrelEvent = process.argv[1];
    if (!squirrelEvent) {
        return false;
    }

    const appFolder = path.resolve(process.execPath, '..');
    const rootFolder = path.resolve(appFolder, '..');
    const updateExe = path.resolve(rootFolder, 'Update.exe');
    const exeName = path.basename(process.execPath);

    const spawnUpdate = function (args) {
        return new Promise((resolve) => {
            try {
                const child = spawn(updateExe, args, { detached: true });
                child.on('close', resolve);
            } catch (e) {
                resolve(-1);
            }
        });
    };

    switch (squirrelEvent) {
        case '--squirrel-install':
        case '--squirrel-updated':
            // Create desktop and Start Menu shortcuts
            spawnUpdate(['--createShortcut', exeName, '--shortcut-locations', 'Desktop,StartMenu']).then(() => {
                app.quit();
            });
            return true;

        case '--squirrel-uninstall':
            // Remove desktop and Start Menu shortcuts
            spawnUpdate(['--removeShortcut', exeName]).then(() => {
                app.quit();
            });
            return true;

        case '--squirrel-obsolete':
            // Called on the outgoing version before update
            app.quit();
            return true;

        default:
            return false;
    }
}

module.exports = { handleSquirrelEvent };

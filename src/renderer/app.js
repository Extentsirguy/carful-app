/**
 * CARFul - Renderer Application
 *
 * Main JavaScript for the CARFul Electron renderer process.
 * Communicates with the Python backend through window.carful API.
 */

// State
const state = {
    currentView: 'dashboard',
    currentFile: null,
    healthCheckResult: null,
    stats: {
        files: 0,
        users: 0,
        transactions: 0,
        validTins: 0
    }
};

// ============================================================
// Navigation
// ============================================================

function navigateTo(viewName) {
    // Hide all views
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));

    // Show target view
    const targetView = document.getElementById(`view-${viewName}`);
    if (targetView) {
        targetView.classList.add('active');
    }

    // Update nav active state
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.view === viewName);
    });

    state.currentView = viewName;
    addLog(`Navigated to ${viewName}`);
}

// ============================================================
// Logging
// ============================================================

function addLog(message) {
    const logContainer = document.getElementById('activity-log');
    const entry = document.createElement('div');
    entry.className = 'log-entry';

    const time = new Date().toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
    });

    entry.innerHTML = `
        <span class="log-time">${time}</span>
        <span class="log-message">${message}</span>
    `;

    logContainer.appendChild(entry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

// ============================================================
// File Import
// ============================================================

function setupDropZone() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    // Click to browse
    dropZone.addEventListener('click', () => fileInput.click());

    // Drag and drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });
}

async function handleFileSelect(file) {
    if (!file.name.endsWith('.csv')) {
        alert('Please select a CSV file.');
        return;
    }

    state.currentFile = file;
    addLog(`Selected file: ${file.name}`);

    // Show preview
    document.getElementById('import-preview').style.display = 'block';
    document.getElementById('file-name').textContent = file.name;
    document.getElementById('file-size').textContent = formatFileSize(file.size);

    // Preview file using RPC
    try {
        const result = await window.carful.rpc.invoke('csv.preview', {
            csv_path: file.path,
            rows: 5
        });

        renderPreviewTable(result.columns, result.rows);
    } catch (error) {
        console.error('Preview error:', error);
        addLog(`Error previewing file: ${error.message}`);
    }
}

function renderPreviewTable(columns, rows) {
    const thead = document.querySelector('#preview-table thead');
    const tbody = document.querySelector('#preview-table tbody');

    thead.innerHTML = '<tr>' + columns.map(c => `<th>${c}</th>`).join('') + '</tr>';
    tbody.innerHTML = rows.map(row =>
        '<tr>' + columns.map(c => `<td>${row[c] ?? ''}</td>`).join('') + '</tr>'
    ).join('');
}

async function startImport() {
    if (!state.currentFile) return;

    addLog('Starting import...');
    showProgress('export-progress');

    try {
        const result = await window.carful.rpc.importCSV(
            state.currentFile.path,
            null // Use temp DB
        );

        addLog(`Import complete: ${result.rows} rows`);
        state.stats.transactions = result.rows;
        updateStats();

        // Run TIN validation
        await runValidation();

    } catch (error) {
        console.error('Import error:', error);
        addLog(`Import error: ${error.message}`);
    } finally {
        hideProgress('export-progress');
    }
}

// ============================================================
// Validation
// ============================================================

async function runValidation() {
    if (!state.currentFile) {
        addLog('No file loaded for validation');
        return;
    }

    addLog('Running TIN validation...');

    try {
        const result = await window.carful.rpc.invoke('tin.validate', {
            csv_path: state.currentFile.path
        });

        // Update UI
        document.getElementById('valid-count').textContent = result.valid;
        document.getElementById('invalid-count').textContent = result.invalid;
        document.getElementById('notin-count').textContent = result.notin;

        state.stats.validTins = result.valid;
        updateStats();

        // Show errors
        renderValidationErrors(result.errors);

        addLog(`Validation: ${result.valid} valid, ${result.invalid} invalid, ${result.notin} NOTIN`);

    } catch (error) {
        console.error('Validation error:', error);
        addLog(`Validation error: ${error.message}`);
    }
}

function renderValidationErrors(errors) {
    const tbody = document.getElementById('error-table-body');
    tbody.innerHTML = errors.map(e => `
        <tr>
            <td>${e.row}</td>
            <td>${e.tin}</td>
            <td>${e.country}</td>
            <td>${e.message}</td>
        </tr>
    `).join('');
}

// ============================================================
// Export
// ============================================================

async function exportXML() {
    if (!state.currentFile) {
        alert('Please import a CSV file first.');
        return;
    }

    // Get output path
    const outputPath = await window.carful.dialog.saveXML('carf_export.xml');
    if (!outputPath) return;

    addLog('Starting XML export...');
    showProgress('export-progress');

    try {
        const config = {
            sending_country: document.getElementById('sending-country').value,
            receiving_country: document.getElementById('receiving-country').value,
            year: parseInt(document.getElementById('reporting-year').value)
        };

        const result = await window.carful.rpc.invoke('xml.export', {
            csv_path: state.currentFile.path,
            output: outputPath,
            config: config
        });

        addLog(`Export complete: ${formatFileSize(result.size)} in ${result.duration.toFixed(2)}s`);
        alert(`Export successful!\n\nFile: ${result.file}\nSize: ${formatFileSize(result.size)}`);

    } catch (error) {
        console.error('Export error:', error);
        addLog(`Export error: ${error.message}`);
        alert(`Export failed: ${error.message}`);
    } finally {
        hideProgress('export-progress');
    }
}

// ============================================================
// Health Check
// ============================================================

async function runHealthCheck() {
    // Get file path
    let csvPath = state.currentFile?.path;
    if (!csvPath) {
        csvPath = await window.carful.dialog.openCSV();
        if (!csvPath) return;
    }

    addLog('Running health check...');

    try {
        const result = await window.carful.rpc.invoke('health.check', {
            csv_path: csvPath
        });

        state.healthCheckResult = result;

        // Update UI
        document.getElementById('health-results').style.display = 'block';
        document.getElementById('health-score').textContent = result.summary.compliance_score;
        document.getElementById('health-grade').textContent = result.summary.grade;

        // Summary
        document.getElementById('health-summary').innerHTML = `
            <p><strong>Total Rows:</strong> ${result.summary.total_rows}</p>
            <p><strong>Valid TINs:</strong> ${result.summary.valid_tins}</p>
            <p><strong>Invalid TINs:</strong> ${result.summary.invalid_tins}</p>
            <p><strong>NOTIN Count:</strong> ${result.summary.notin_count}</p>
            <p><strong>Filing Ready:</strong> ${result.summary.filing_ready ? 'Yes ✅' : 'No ❌'}</p>
        `;

        addLog(`Health check complete: Score ${result.summary.compliance_score}% (${result.summary.grade})`);

    } catch (error) {
        console.error('Health check error:', error);
        addLog(`Health check error: ${error.message}`);
    }
}

async function downloadHealthReport() {
    if (!state.healthCheckResult) {
        alert('Please run a health check first.');
        return;
    }

    const outputPath = await window.carful.dialog.savePDF('health_check_report.pdf');
    if (!outputPath) return;

    try {
        const result = await window.carful.rpc.invoke('report.pdf', {
            check_result: state.healthCheckResult,
            output: outputPath
        });

        addLog(`PDF report saved: ${outputPath}`);
        alert(`Report saved to:\n${outputPath}`);

    } catch (error) {
        console.error('PDF error:', error);
        addLog(`PDF error: ${error.message}`);
    }
}

// ============================================================
// Settings
// ============================================================

async function loadSettings() {
    try {
        const settings = await window.carful.settings.getAll();
        if (settings) {
            if (settings.rcasp_name) document.getElementById('rcasp-name').value = settings.rcasp_name;
            if (settings.rcasp_tin) document.getElementById('rcasp-tin').value = settings.rcasp_tin;
            if (settings.rcasp_country) document.getElementById('rcasp-country').value = settings.rcasp_country;
            if (settings.rcasp_city) document.getElementById('rcasp-city').value = settings.rcasp_city;
            if (settings.rcasp_street) document.getElementById('rcasp-street').value = settings.rcasp_street;
        }
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

async function saveSettings() {
    try {
        await window.carful.settings.set('rcasp_name', document.getElementById('rcasp-name').value);
        await window.carful.settings.set('rcasp_tin', document.getElementById('rcasp-tin').value);
        await window.carful.settings.set('rcasp_country', document.getElementById('rcasp-country').value);
        await window.carful.settings.set('rcasp_city', document.getElementById('rcasp-city').value);
        await window.carful.settings.set('rcasp_street', document.getElementById('rcasp-street').value);

        addLog('Settings saved');
        alert('Settings saved successfully!');
    } catch (error) {
        console.error('Failed to save settings:', error);
        alert('Failed to save settings.');
    }
}

// ============================================================
// UI Helpers
// ============================================================

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function updateStats() {
    document.getElementById('stat-files').textContent = state.stats.files || 0;
    document.getElementById('stat-users').textContent = state.stats.users || 0;
    document.getElementById('stat-transactions').textContent = state.stats.transactions || 0;
    document.getElementById('stat-tin-valid').textContent = state.stats.validTins || 0;
}

function showProgress(containerId) {
    const container = document.getElementById(containerId);
    if (container) container.style.display = 'block';
}

function hideProgress(containerId) {
    const container = document.getElementById(containerId);
    if (container) container.style.display = 'none';
}

function updateProgress(percent, message) {
    const fill = document.getElementById('progress-fill');
    const text = document.getElementById('progress-text');
    if (fill) fill.style.width = percent + '%';
    if (text) text.textContent = message || `${percent}%`;
}

// ============================================================
// Initialization
// ============================================================

async function init() {
    // Setup navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            navigateTo(item.dataset.view);
        });
    });

    // Setup drop zone
    setupDropZone();

    // Setup buttons
    document.getElementById('btn-quick-import')?.addEventListener('click', () => navigateTo('import'));
    document.getElementById('btn-quick-export')?.addEventListener('click', () => navigateTo('export'));
    document.getElementById('btn-quick-health')?.addEventListener('click', () => navigateTo('health-check'));

    document.getElementById('btn-start-import')?.addEventListener('click', startImport);
    document.getElementById('btn-cancel-import')?.addEventListener('click', () => {
        document.getElementById('import-preview').style.display = 'none';
        state.currentFile = null;
    });

    document.getElementById('btn-export')?.addEventListener('click', exportXML);
    document.getElementById('btn-health-check')?.addEventListener('click', runHealthCheck);
    document.getElementById('btn-download-report')?.addEventListener('click', downloadHealthReport);
    document.getElementById('btn-save-settings')?.addEventListener('click', saveSettings);

    // Settings tabs
    document.querySelectorAll('.settings-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.settings-panel').forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`panel-${tab.dataset.tab}`)?.classList.add('active');
        });
    });

    // Load app info
    try {
        const version = await window.carful.app.getVersion();
        document.getElementById('app-version').textContent = `v${version}`;
        document.getElementById('status-version').textContent = `v${version}`;
    } catch (error) {
        console.log('Could not get app version');
    }

    // Load settings
    await loadSettings();

    // Setup progress listener
    if (window.carful?.events?.onProgress) {
        window.carful.events.onProgress((percent, message) => {
            updateProgress(percent, message);
        });
    }

    addLog('CARFul initialized');
    updateStats();
}

// Start app when DOM ready
document.addEventListener('DOMContentLoaded', init);

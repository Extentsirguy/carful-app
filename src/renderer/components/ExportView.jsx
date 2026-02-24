import React, { useState, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { useRPC } from '../hooks/useRPC';
import ProgressBar from './ProgressBar';
import UpgradePrompt from './UpgradePrompt';
import {
  Download,
  FileText,
  CheckCircle,
  AlertTriangle,
  Folder,
  Settings,
  Lock,
} from 'lucide-react';

const COUNTRIES = [
  { code: 'US', name: 'United States' },
  { code: 'GB', name: 'United Kingdom' },
  { code: 'CA', name: 'Canada' },
  { code: 'DE', name: 'Germany' },
  { code: 'FR', name: 'France' },
  { code: 'CH', name: 'Switzerland' },
  { code: 'SG', name: 'Singapore' },
  { code: 'AU', name: 'Australia' },
];

function ExportView() {
  const { state, actions, isPro } = useApp();
  const { invoke } = useRPC();
  const { dbPath, importFile, settings, exporting } = state;
  const { export: exportSettings, rcasp } = settings;

  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [showUpgrade, setShowUpgrade] = useState(false);
  const [localSettings, setLocalSettings] = useState({
    sendingCountry: exportSettings.sendingCountry,
    receivingCountry: exportSettings.receivingCountry,
    reportingYear: exportSettings.reportingYear,
  });

  const handleExport = useCallback(async () => {
    // Check Pro status first
    if (!isPro) {
      setShowUpgrade(true);
      return;
    }

    if (!dbPath && !importFile?.path) {
      actions.addLog('No data imported. Please import a CSV file first.');
      return;
    }

    // Get save location
    const outputPath = await window.carful?.dialog?.saveXML(
      `carf_${localSettings.sendingCountry}_${localSettings.receivingCountry}_${localSettings.reportingYear}.xml`
    );

    if (!outputPath) {
      actions.addLog('Export cancelled - no output file selected');
      return;
    }

    actions.setExporting(true);
    setProgress(0);
    setResult(null);
    actions.addLog('Starting CARF XML export...');

    try {
      // Simulate progress updates
      const progressInterval = setInterval(() => {
        setProgress((p) => Math.min(p + 5, 90));
      }, 200);

      const exportResult = await invoke('xml.export', {
        csv_path: importFile?.path,
        db_path: dbPath,
        output: outputPath,
        config: {
          sending_country: localSettings.sendingCountry,
          receiving_country: localSettings.receivingCountry,
          reporting_year: localSettings.reportingYear,
          rcasp: {
            name: rcasp.name,
            tin: rcasp.tin,
            country: rcasp.country,
            city: rcasp.city,
            street: rcasp.street,
          },
        },
      });

      clearInterval(progressInterval);
      setProgress(100);

      setResult({
        success: true,
        file: exportResult.file,
        size: exportResult.size,
        duration: exportResult.duration,
      });

      actions.setLastExport(exportResult);
      actions.addLog(
        `Export complete: ${exportResult.file} (${(exportResult.size / 1024).toFixed(1)} KB)`
      );
    } catch (error) {
      setResult({
        success: false,
        error: error.message,
      });
      actions.addLog(`Export failed: ${error.message}`);
    } finally {
      actions.setExporting(false);
    }
  }, [dbPath, importFile, localSettings, rcasp, invoke, actions]);

  const isConfigValid = rcasp.name && rcasp.tin && rcasp.country;

  return (
    <div className="space-y-6">
      {/* Upgrade Prompt Modal */}
      <UpgradePrompt
        isOpen={showUpgrade}
        onDismiss={() => setShowUpgrade(false)}
        onEnterLicense={() => actions.setView('settings')}
        onViewPlans={() => setShowUpgrade(false)}
      />

      {/* Header */}
      <header>
        <h2 className="text-2xl font-bold text-slate-900">Export XML</h2>
        <p className="text-slate-500">Generate CARF-compliant XML file</p>
      </header>

      {/* Pro Feature Banner (when not Pro) */}
      {!isPro && (
        <div className="card bg-carful-50 border-carful-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Lock className="w-5 h-5 text-carful-600 flex-shrink-0" />
              <div>
                <p className="font-semibold text-carful-900">XML export requires CARFul Pro</p>
                <p className="text-sm text-carful-700">Unlock Pro features to export CARF XML</p>
              </div>
            </div>
            <button
              onClick={() => actions.setView('settings')}
              className="btn btn-carful btn-sm"
            >
              Upgrade Now
            </button>
          </div>
        </div>
      )}

      {/* No data warning */}
      {!dbPath && !importFile?.path && (
        <div className="card bg-warning-50 border-warning-200">
          <div className="flex items-start gap-4">
            <AlertTriangle className="w-6 h-6 text-warning-600 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-warning-900">No Data Imported</h3>
              <p className="text-warning-700 mt-1">
                Please import a CSV file before exporting.
              </p>
              <button
                onClick={() => actions.setView('import')}
                className="btn btn-secondary mt-3"
              >
                Go to Import
              </button>
            </div>
          </div>
        </div>
      )}

      {/* RCASP config warning */}
      {!isConfigValid && (
        <div className="card bg-warning-50 border-warning-200">
          <div className="flex items-start gap-4">
            <Settings className="w-6 h-6 text-warning-600 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-warning-900">
                RCASP Configuration Required
              </h3>
              <p className="text-warning-700 mt-1">
                Please configure your RCASP details in Settings before exporting.
              </p>
              <button
                onClick={() => actions.setView('settings')}
                className="btn btn-secondary mt-3"
              >
                Configure Settings
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Export configuration */}
      {(dbPath || importFile?.path) && (
        <div className="card">
          <h3 className="font-semibold text-slate-900 mb-4">Export Configuration</h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div>
              <label className="label">Transmitting Country</label>
              <select
                value={localSettings.sendingCountry}
                onChange={(e) =>
                  setLocalSettings({ ...localSettings, sendingCountry: e.target.value })
                }
                className="select"
              >
                {COUNTRIES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name} ({c.code})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="label">Receiving Country</label>
              <select
                value={localSettings.receivingCountry}
                onChange={(e) =>
                  setLocalSettings({ ...localSettings, receivingCountry: e.target.value })
                }
                className="select"
              >
                {COUNTRIES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name} ({c.code})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="label">Reporting Year</label>
              <input
                type="number"
                value={localSettings.reportingYear}
                onChange={(e) =>
                  setLocalSettings({
                    ...localSettings,
                    reportingYear: parseInt(e.target.value),
                  })
                }
                min="2020"
                max="2030"
                className="input"
              />
            </div>
          </div>

          {/* RCASP summary */}
          {isConfigValid && (
            <div className="p-4 bg-slate-50 rounded-lg mb-6">
              <h4 className="text-sm font-medium text-slate-600 mb-2">RCASP Details</h4>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <span className="text-slate-500">Company:</span>
                <span className="text-slate-900">{rcasp.name}</span>
                <span className="text-slate-500">TIN:</span>
                <span className="text-slate-900 font-mono">{rcasp.tin}</span>
                <span className="text-slate-500">Country:</span>
                <span className="text-slate-900">{rcasp.country}</span>
              </div>
            </div>
          )}

          {/* Export button */}
          <button
            onClick={handleExport}
            disabled={exporting || !isConfigValid || !isPro}
            className="btn btn-primary btn-large w-full"
          >
            {isPro ? (
              <>
                <Download className="w-5 h-5" />
                {exporting ? 'Exporting...' : 'Export CARF XML'}
              </>
            ) : (
              <>
                <Lock className="w-5 h-5" />
                Pro Feature - Upgrade to Export
              </>
            )}
          </button>
        </div>
      )}

      {/* Progress */}
      {exporting && (
        <div className="card">
          <h3 className="font-semibold text-slate-900 mb-4">Generating XML...</h3>
          <ProgressBar
            progress={progress}
            message="Building CARF-compliant XML structure..."
            showTime
          />
        </div>
      )}

      {/* Result */}
      {result && (
        <div
          className={`card ${
            result.success ? 'bg-success-50 border-success-200' : 'bg-error-50 border-error-200'
          }`}
        >
          <div className="flex items-start gap-4">
            {result.success ? (
              <CheckCircle className="w-8 h-8 text-success-600 flex-shrink-0" />
            ) : (
              <AlertTriangle className="w-8 h-8 text-error-600 flex-shrink-0" />
            )}
            <div className="flex-1">
              <h3 className="font-semibold text-slate-900">
                {result.success ? 'Export Successful!' : 'Export Failed'}
              </h3>
              {result.success ? (
                <div className="mt-2 space-y-1 text-sm text-slate-600">
                  <p className="flex items-center gap-2">
                    <FileText className="w-4 h-4" />
                    {result.file}
                  </p>
                  <p>
                    Size: {(result.size / 1024).toFixed(1)} KB • Duration:{' '}
                    {result.duration.toFixed(2)}s
                  </p>
                </div>
              ) : (
                <p className="text-error-600 mt-2">{result.error}</p>
              )}
            </div>
          </div>

          {result.success && (
            <div className="mt-4 pt-4 border-t border-success-200 flex gap-3">
              <button
                onClick={() => {
                  window.carful?.shell?.showItemInFolder(result.file);
                }}
                className="btn btn-secondary"
              >
                <Folder className="w-4 h-4" />
                Show in Folder
              </button>
              <button
                onClick={() => {
                  setResult(null);
                  setProgress(0);
                }}
                className="btn btn-primary"
              >
                Export Another
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ExportView;

import React, { useState, useCallback, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { useRPC } from '../hooks/useRPC';
import LicenseManager from './LicenseManager';
import { Save, RefreshCw, CheckCircle, AlertCircle, Key } from 'lucide-react';

const COUNTRIES = [
  { code: 'US', name: 'United States' },
  { code: 'GB', name: 'United Kingdom' },
  { code: 'CA', name: 'Canada' },
  { code: 'DE', name: 'Germany' },
  { code: 'FR', name: 'France' },
  { code: 'CH', name: 'Switzerland' },
  { code: 'SG', name: 'Singapore' },
  { code: 'AU', name: 'Australia' },
  { code: 'JP', name: 'Japan' },
  { code: 'HK', name: 'Hong Kong' },
];

const TABS = [
  { id: 'rcasp', label: 'RCASP Profile' },
  { id: 'export', label: 'Export Options' },
  { id: 'advanced', label: 'Advanced' },
  { id: 'license', label: 'License', icon: Key },
];

function SettingsPanel() {
  const { state, actions, isPro } = useApp();
  const { validateSingleTIN, loading } = useRPC();
  const [activeTab, setActiveTab] = useState('rcasp');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [tinStatus, setTinStatus] = useState(null);

  const { rcasp, export: exportSettings, advanced = {} } = state.settings;
  const { license } = state;

  // Validate TIN when it changes
  const validateTIN = useCallback(async () => {
    if (!rcasp.tin || !rcasp.country) {
      setTinStatus(null);
      return;
    }

    try {
      const result = await validateSingleTIN(rcasp.tin, rcasp.country);
      setTinStatus(result);
    } catch (error) {
      setTinStatus({ valid: false, error: error.message });
    }
  }, [rcasp.tin, rcasp.country, validateSingleTIN]);

  useEffect(() => {
    const timeout = setTimeout(validateTIN, 500);
    return () => clearTimeout(timeout);
  }, [rcasp.tin, rcasp.country, validateTIN]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      // Save settings using electron-store
      if (window.carful?.settings?.set) {
        await window.carful.settings.set('rcasp', rcasp);
        await window.carful.settings.set('export', exportSettings);
        await window.carful.settings.set('advanced', advanced);
      }
      setSaved(true);
      actions.addLog('Settings saved successfully');
      setTimeout(() => setSaved(false), 2000);
    } catch (error) {
      console.error('Failed to save settings:', error);
      actions.addLog(`Failed to save settings: ${error.message}`);
    } finally {
      setSaving(false);
    }
  }, [rcasp, exportSettings, advanced, actions]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Settings</h2>
          <p className="text-slate-500">Configure CARFul preferences</p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="btn btn-primary"
        >
          {saving ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : saved ? (
            <CheckCircle className="w-4 h-4" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          {saved ? 'Saved!' : 'Save Settings'}
        </button>
      </header>

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="flex gap-1">
          {TABS.map((tab) => {
            const isLicenseTab = tab.id === 'license';
            const TabIcon = tab.icon;

            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  px-4 py-2.5 font-medium text-sm border-b-2 transition-colors
                  flex items-center gap-2
                  ${
                    activeTab === tab.id
                      ? 'border-carful-600 text-carful-600'
                      : 'border-transparent text-slate-500 hover:text-slate-700'
                  }
                `}
              >
                {TabIcon && <TabIcon className="w-4 h-4" />}
                {tab.label}
                {isLicenseTab && (
                  <span
                    className={`ml-2 w-2 h-2 rounded-full ${
                      isPro ? 'bg-success-500' : 'bg-slate-400'
                    }`}
                  />
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* RCASP Profile Tab */}
      {activeTab === 'rcasp' && (
        <div className="card">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">
            Reporting Crypto-Asset Service Provider
          </h3>
          <p className="text-sm text-slate-500 mb-6">
            Enter your company details as they should appear in CARF XML filings.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="label">Company Name</label>
              <input
                type="text"
                value={rcasp.name}
                onChange={(e) => actions.updateRCASP({ name: e.target.value })}
                placeholder="Your Company Name"
                className="input"
              />
            </div>

            <div>
              <label className="label">Country</label>
              <select
                value={rcasp.country}
                onChange={(e) => actions.updateRCASP({ country: e.target.value })}
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
              <label className="label">
                TIN (Tax Identification Number)
                {tinStatus && (
                  <span
                    className={`ml-2 text-xs ${
                      tinStatus.valid ? 'text-success-600' : 'text-error-600'
                    }`}
                  >
                    {tinStatus.valid ? '✓ Valid' : '✗ Invalid'}
                  </span>
                )}
              </label>
              <input
                type="text"
                value={rcasp.tin}
                onChange={(e) => actions.updateRCASP({ tin: e.target.value })}
                placeholder="12-3456789"
                className={`input ${
                  tinStatus
                    ? tinStatus.valid
                      ? 'border-success-500'
                      : 'border-error-500'
                    : ''
                }`}
              />
              {tinStatus && !tinStatus.valid && tinStatus.error && (
                <p className="text-xs text-error-600 mt-1">{tinStatus.error}</p>
              )}
            </div>

            <div>
              <label className="label">City</label>
              <input
                type="text"
                value={rcasp.city}
                onChange={(e) => actions.updateRCASP({ city: e.target.value })}
                placeholder="New York"
                className="input"
              />
            </div>

            <div>
              <label className="label">Street Address</label>
              <input
                type="text"
                value={rcasp.street}
                onChange={(e) => actions.updateRCASP({ street: e.target.value })}
                placeholder="123 Main Street"
                className="input"
              />
            </div>
          </div>
        </div>
      )}

      {/* Export Options Tab */}
      {activeTab === 'export' && (
        <div className="card">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Export Options</h3>
          <p className="text-sm text-slate-500 mb-6">
            Configure default settings for CARF XML exports.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Transmitting Country</label>
              <select
                value={exportSettings.sendingCountry}
                onChange={(e) =>
                  actions.updateExportOptions({ sendingCountry: e.target.value })
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
                value={exportSettings.receivingCountry}
                onChange={(e) =>
                  actions.updateExportOptions({ receivingCountry: e.target.value })
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
                value={exportSettings.reportingYear}
                onChange={(e) =>
                  actions.updateExportOptions({ reportingYear: parseInt(e.target.value) })
                }
                min="2020"
                max="2030"
                className="input"
              />
            </div>

            <div>
              <label className="label">Message Type</label>
              <select
                value={exportSettings.messageType}
                onChange={(e) =>
                  actions.updateExportOptions({ messageType: e.target.value })
                }
                className="select"
              >
                <option value="CARF1">CARF1 - New Data</option>
                <option value="CARF2">CARF2 - Corrected Data</option>
                <option value="CARF3">CARF3 - Nil Report</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Advanced Tab */}
      {activeTab === 'advanced' && (
        <div className="card">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Advanced Settings</h3>
          <p className="text-sm text-slate-500 mb-6">
            Configure advanced options for power users.
          </p>

          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
              <div>
                <p className="font-medium text-slate-900">Validation Strictness</p>
                <p className="text-sm text-slate-500">
                  How strictly to validate TIN formats
                </p>
              </div>
              <select
                value={advanced.validationStrictness || 'strict'}
                onChange={(e) => actions.updateAdvanced({ validationStrictness: e.target.value })}
                className="select w-auto"
              >
                <option value="strict">Strict</option>
                <option value="lenient">Lenient</option>
              </select>
            </div>

            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
              <div>
                <p className="font-medium text-slate-900">Auto-Update</p>
                <p className="text-sm text-slate-500">
                  Automatically check for updates on startup
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={advanced.autoUpdate !== false}
                  onChange={(e) => actions.updateAdvanced({ autoUpdate: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-300 peer-focus:ring-2 peer-focus:ring-carful-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-carful-600 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
              </label>
            </div>

            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
              <div>
                <p className="font-medium text-slate-900">Debug Mode</p>
                <p className="text-sm text-slate-500">
                  Enable verbose logging for troubleshooting
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={advanced.debugMode || false}
                  onChange={(e) => actions.updateAdvanced({ debugMode: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-300 peer-focus:ring-2 peer-focus:ring-carful-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-carful-600 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
              </label>
            </div>
          </div>
        </div>
      )}

      {/* License Tab */}
      {activeTab === 'license' && (
        <LicenseManager />
      )}
    </div>
  );
}

export default SettingsPanel;

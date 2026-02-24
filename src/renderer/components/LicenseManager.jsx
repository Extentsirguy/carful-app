import React, { useState, useCallback, useEffect } from 'react';
import { Key, Check, AlertCircle, Loader, Copy, ExternalLink } from 'lucide-react';
import { useApp } from '../context/AppContext';

const LICENSE_KEY_REGEX = /^CARF-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/;
const API_BASE_URL = import.meta.env?.VITE_API_URL || 'https://api.carful.app';

function LicenseManager() {
  const { state, actions } = useApp();
  const { license } = state;

  const [keyInput, setKeyInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [machineId, setMachineId] = useState(null);
  const [copiedToClipboard, setCopiedToClipboard] = useState(false);

  // Get machine ID on mount
  useEffect(() => {
    async function getMachineId() {
      try {
        const id = await window.carful?.license?.getMachineId();
        setMachineId(id);
      } catch (error) {
        console.error('Failed to get machine ID:', error);
      }
    }
    getMachineId();
  }, []);

  // Validate license key format
  const isValidKeyFormat = (key) => {
    return LICENSE_KEY_REGEX.test(key.trim().toUpperCase());
  };

  // Format license key for display
  const formatLicenseKey = (key) => {
    if (!key) return '';
    return key.toUpperCase();
  };

  // Copy machine ID to clipboard
  const copyMachineId = useCallback(() => {
    if (machineId) {
      navigator.clipboard.writeText(machineId).then(() => {
        setCopiedToClipboard(true);
        setTimeout(() => setCopiedToClipboard(false), 2000);
      });
    }
  }, [machineId]);

  // Activate license
  const handleActivate = useCallback(async () => {
    const trimmedKey = keyInput.trim().toUpperCase();

    // Validate format
    if (!isValidKeyFormat(trimmedKey)) {
      setError('Invalid license key format. Expected: CARF-XXXX-XXXX-XXXX-XXXX');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      // First, verify the license key
      const verifyResponse = await fetch(`${API_BASE_URL}/api/verify-license`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          license_key: trimmedKey,
        }),
      });

      if (!verifyResponse.ok) {
        const data = await verifyResponse.json();
        throw new Error(data.error || 'Invalid license key');
      }

      const verifyData = await verifyResponse.json();

      // Then, activate the license
      const activateResponse = await fetch(`${API_BASE_URL}/api/activate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          license_key: trimmedKey,
          machine_id: machineId,
        }),
      });

      if (!activateResponse.ok) {
        const data = await activateResponse.json();
        throw new Error(data.error || 'Failed to activate license');
      }

      const activateData = await activateResponse.json();

      // Store license data locally
      const licenseData = {
        key: trimmedKey,
        email: activateData.email,
        status: activateData.status || 'active',
        expiresAt: activateData.expires_at,
        machineId: machineId,
        activatedAt: new Date().toISOString(),
      };

      await window.carful?.license?.set(licenseData);
      actions.setLicense(licenseData);

      setKeyInput('');
      setSuccess(`License activated successfully! Welcome, ${activateData.email}`);
      actions.addLog(`License activated: ${trimmedKey}`);

      // Clear success message after 5 seconds
      setTimeout(() => setSuccess(null), 5000);
    } catch (err) {
      console.error('License activation error:', err);
      const errorMsg = err.message || 'Failed to activate license. Please check your key and try again.';
      setError(errorMsg);
      actions.addLog(`License activation failed: ${errorMsg}`);
    } finally {
      setLoading(false);
    }
  }, [keyInput, machineId, actions]);

  // Deactivate license
  const handleDeactivate = useCallback(async () => {
    if (!window.confirm('Are you sure you want to deactivate this license? You will lose Pro features.')) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await window.carful?.license?.clear();
      actions.clearLicense();
      setSuccess('License deactivated');
      actions.addLog('License deactivated');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      console.error('Deactivation error:', err);
      setError('Failed to deactivate license');
    } finally {
      setLoading(false);
    }
  }, [actions]);

  // Format expiry date
  const formatExpiryDate = (isoString) => {
    if (!isoString) return 'Unknown';
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });
    } catch {
      return 'Unknown';
    }
  };

  // Check if license is expired
  const isExpired = license?.expiresAt && new Date(license.expiresAt) < new Date();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h3 className="text-lg font-semibold text-slate-900">License Management</h3>
        <p className="text-sm text-slate-500 mt-1">
          Manage your CARFul Pro license to unlock advanced features
        </p>
      </div>

      {/* No License - Input Section */}
      {!license?.key && (
        <div className="card">
          <div className="flex items-start gap-4 mb-6">
            <div className="w-12 h-12 bg-slate-100 rounded-lg flex items-center justify-center">
              <Key className="w-6 h-6 text-slate-600" />
            </div>
            <div className="flex-1">
              <h4 className="font-semibold text-slate-900">Free Plan</h4>
              <p className="text-sm text-slate-500 mt-1">
                You're currently using CARFul Free. Upgrade to Pro for XML export and more.
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="label">License Key</label>
              <input
                type="text"
                value={keyInput}
                onChange={(e) => {
                  setKeyInput(e.target.value);
                  setError(null);
                }}
                placeholder="CARF-XXXX-XXXX-XXXX-XXXX"
                className={`input ${error ? 'border-error-500' : ''}`}
                disabled={loading}
              />
              <p className="text-xs text-slate-500 mt-2">
                Format: CARF-XXXX-XXXX-XXXX-XXXX (alphanumeric)
              </p>
            </div>

            {error && (
              <div className="flex items-start gap-3 p-3 bg-error-50 rounded-lg border border-error-200">
                <AlertCircle className="w-5 h-5 text-error-600 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-error-700">{error}</p>
              </div>
            )}

            {success && (
              <div className="flex items-start gap-3 p-3 bg-success-50 rounded-lg border border-success-200">
                <Check className="w-5 h-5 text-success-600 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-success-700">{success}</p>
              </div>
            )}

            <button
              onClick={handleActivate}
              disabled={loading || !keyInput.trim()}
              className="btn btn-primary w-full"
            >
              {loading ? (
                <>
                  <Loader className="w-4 h-4 animate-spin" />
                  Activating...
                </>
              ) : (
                <>
                  <Key className="w-4 h-4" />
                  Activate License
                </>
              )}
            </button>

            <div className="p-4 bg-slate-50 rounded-lg">
              <p className="text-xs font-medium text-slate-700 mb-2">Don't have a license?</p>
              <a
                href="https://carful.app/#pricing"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-sm text-carful-600 hover:text-carful-700 font-medium"
              >
                View CARFul Pro Plans
                <ExternalLink className="w-4 h-4" />
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Active License - Display Section */}
      {license?.key && !isExpired && (
        <div className="card border-success-200 bg-success-50">
          <div className="flex items-start gap-4 mb-6">
            <div className="w-12 h-12 bg-success-100 rounded-lg flex items-center justify-center">
              <Check className="w-6 h-6 text-success-600" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h4 className="font-semibold text-success-900">CARFul Pro</h4>
                <span className="px-2 py-1 bg-success-600 text-white text-xs font-semibold rounded-full">
                  Active
                </span>
              </div>
              <p className="text-sm text-success-800 mt-1">
                Your Pro features are unlocked and ready to use
              </p>
            </div>
          </div>

          <div className="space-y-4 mb-6">
            <div className="p-4 bg-white rounded-lg border border-success-200">
              <p className="text-xs font-medium text-slate-600 mb-1">Email</p>
              <p className="text-sm font-mono text-slate-900">{license.email}</p>
            </div>

            <div className="p-4 bg-white rounded-lg border border-success-200">
              <p className="text-xs font-medium text-slate-600 mb-1">License Key</p>
              <p className="text-sm font-mono text-slate-900">{license.key}</p>
            </div>

            <div className="p-4 bg-white rounded-lg border border-success-200">
              <p className="text-xs font-medium text-slate-600 mb-1">Expires</p>
              <p className="text-sm text-slate-900">{formatExpiryDate(license.expiresAt)}</p>
            </div>
          </div>

          <button
            onClick={handleDeactivate}
            disabled={loading}
            className="btn btn-secondary w-full"
          >
            {loading ? (
              <>
                <Loader className="w-4 h-4 animate-spin" />
                Deactivating...
              </>
            ) : (
              'Deactivate License'
            )}
          </button>
        </div>
      )}

      {/* Expired License - Display Section */}
      {license?.key && isExpired && (
        <div className="card border-warning-200 bg-warning-50">
          <div className="flex items-start gap-4 mb-6">
            <div className="w-12 h-12 bg-warning-100 rounded-lg flex items-center justify-center">
              <AlertCircle className="w-6 h-6 text-warning-600" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h4 className="font-semibold text-warning-900">License Expired</h4>
                <span className="px-2 py-1 bg-warning-600 text-white text-xs font-semibold rounded-full">
                  Expired
                </span>
              </div>
              <p className="text-sm text-warning-800 mt-1">
                Your Pro license has expired. Renew to continue using Pro features.
              </p>
            </div>
          </div>

          <div className="space-y-4 mb-6">
            <div className="p-4 bg-white rounded-lg border border-warning-200">
              <p className="text-xs font-medium text-slate-600 mb-1">Email</p>
              <p className="text-sm font-mono text-slate-900">{license.email}</p>
            </div>

            <div className="p-4 bg-white rounded-lg border border-warning-200">
              <p className="text-xs font-medium text-slate-600 mb-1">Expired At</p>
              <p className="text-sm text-slate-900">{formatExpiryDate(license.expiresAt)}</p>
            </div>
          </div>

          <div className="space-y-3">
            <a
              href="https://carful.app/#pricing"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-primary w-full inline-flex justify-center items-center gap-2"
            >
              Renew License
              <ExternalLink className="w-4 h-4" />
            </a>

            <button
              onClick={handleDeactivate}
              className="btn btn-outline w-full"
            >
              Remove License
            </button>
          </div>
        </div>
      )}

      {/* Machine ID Info */}
      <div className="card bg-slate-50">
        <h4 className="font-semibold text-slate-900 mb-4">Machine Information</h4>
        <p className="text-sm text-slate-600 mb-4">
          Your unique machine identifier is used to activate licenses on this device.
        </p>

        <div className="p-3 bg-white rounded-lg border border-slate-200 flex items-center justify-between">
          <code className="text-xs text-slate-700 break-all font-mono">{machineId || 'Loading...'}</code>
          <button
            onClick={copyMachineId}
            disabled={!machineId}
            className="ml-2 p-2 hover:bg-slate-100 rounded transition-colors flex-shrink-0"
            title="Copy to clipboard"
          >
            <Copy
              className={`w-4 h-4 ${
                copiedToClipboard ? 'text-success-600' : 'text-slate-600'
              }`}
            />
          </button>
        </div>
        {copiedToClipboard && (
          <p className="text-xs text-success-600 mt-2">Copied to clipboard!</p>
        )}
      </div>
    </div>
  );
}

export default LicenseManager;

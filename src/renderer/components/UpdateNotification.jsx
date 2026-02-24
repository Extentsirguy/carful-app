import React, { useState, useEffect, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import {
  Download,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  X,
  ArrowRight,
  Sparkles,
} from 'lucide-react';
import ProgressBar from './ProgressBar';

function UpdateNotification() {
  const { actions } = useApp();
  const [updateStatus, setUpdateStatus] = useState(null);
  const [updateInfo, setUpdateInfo] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [dismissed, setDismissed] = useState(false);

  // Listen for update events from main process
  useEffect(() => {
    if (!window.carful?.events) return;

    const handleUpdateStatus = (status, data) => {
      setUpdateStatus(status);

      switch (status) {
        case 'available':
          setUpdateInfo(data);
          setDismissed(false);
          break;
        case 'progress':
          setDownloadProgress(data.percent);
          break;
        case 'downloaded':
          setUpdateInfo(data);
          setDownloading(false);
          break;
        case 'error':
          setDownloading(false);
          actions.addLog(`Update error: ${data.message}`);
          break;
        default:
          break;
      }
    };

    // Subscribe to update events
    const cleanup = window.carful.events.onUpdateAvailable?.((version, releaseNotes) => {
      handleUpdateStatus('available', { version, releaseNotes });
    });

    return cleanup;
  }, [actions]);

  // Check for updates on mount
  useEffect(() => {
    const checkUpdates = async () => {
      try {
        // This will trigger the update events if an update is available
        await window.carful?.rpc?.invoke?.('update.check');
      } catch (error) {
        console.error('Failed to check for updates:', error);
      }
    };

    // Check after a short delay
    const timeout = setTimeout(checkUpdates, 5000);
    return () => clearTimeout(timeout);
  }, []);

  const handleDownload = useCallback(async () => {
    setDownloading(true);
    setDownloadProgress(0);
    actions.addLog('Downloading update...');

    try {
      await window.carful?.rpc?.invoke?.('update.download');
    } catch (error) {
      actions.addLog(`Download failed: ${error.message}`);
      setDownloading(false);
    }
  }, [actions]);

  const handleInstall = useCallback(async () => {
    actions.addLog('Installing update and restarting...');
    try {
      await window.carful?.rpc?.invoke?.('update.install');
    } catch (error) {
      actions.addLog(`Install failed: ${error.message}`);
    }
  }, [actions]);

  const handleDismiss = useCallback(() => {
    setDismissed(true);
  }, []);

  // Don't render if no update or dismissed
  if (!updateInfo || dismissed || updateStatus === 'not-available') {
    return null;
  }

  // Update downloaded - show install prompt
  if (updateStatus === 'downloaded') {
    return (
      <div className="fixed bottom-4 right-4 w-80 bg-white rounded-xl shadow-lg border border-success-200 overflow-hidden z-50">
        <div className="p-4 bg-success-50">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-success-600" />
              <h4 className="font-semibold text-success-900">Update Ready</h4>
            </div>
            <button
              onClick={handleDismiss}
              className="p-1 hover:bg-success-100 rounded transition-colors"
            >
              <X className="w-4 h-4 text-success-600" />
            </button>
          </div>
          <p className="text-sm text-success-700 mt-2">
            Version {updateInfo.version} has been downloaded and is ready to install.
          </p>
        </div>
        <div className="p-4 flex gap-2">
          <button
            onClick={handleInstall}
            className="btn btn-success flex-1"
          >
            <RefreshCw className="w-4 h-4" />
            Restart & Install
          </button>
          <button
            onClick={handleDismiss}
            className="btn btn-secondary"
          >
            Later
          </button>
        </div>
      </div>
    );
  }

  // Downloading - show progress
  if (downloading) {
    return (
      <div className="fixed bottom-4 right-4 w-80 bg-white rounded-xl shadow-lg border border-slate-200 overflow-hidden z-50">
        <div className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <Download className="w-5 h-5 text-carful-600 animate-bounce" />
            <h4 className="font-semibold text-slate-900">Downloading Update</h4>
          </div>
          <ProgressBar
            progress={downloadProgress}
            message={`Downloading v${updateInfo.version}...`}
            showPercentage
          />
        </div>
      </div>
    );
  }

  // Update available - show prompt
  if (updateStatus === 'available') {
    return (
      <div className="fixed bottom-4 right-4 w-80 bg-white rounded-xl shadow-lg border border-carful-200 overflow-hidden z-50">
        <div className="p-4 bg-gradient-to-r from-carful-50 to-purple-50">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-carful-600" />
              <h4 className="font-semibold text-carful-900">Update Available</h4>
            </div>
            <button
              onClick={handleDismiss}
              className="p-1 hover:bg-carful-100 rounded transition-colors"
            >
              <X className="w-4 h-4 text-carful-600" />
            </button>
          </div>
          <p className="text-sm text-carful-700 mt-2">
            CARFul v{updateInfo.version} is now available.
          </p>
        </div>

        {/* Release notes preview */}
        {updateInfo.releaseNotes && (
          <div className="px-4 py-3 border-t border-slate-100">
            <p className="text-xs text-slate-500 mb-1">What's new:</p>
            <p className="text-sm text-slate-600 line-clamp-3">
              {typeof updateInfo.releaseNotes === 'string'
                ? updateInfo.releaseNotes.substring(0, 150)
                : 'Bug fixes and improvements'}
              ...
            </p>
          </div>
        )}

        <div className="p-4 border-t border-slate-100 flex gap-2">
          <button
            onClick={handleDownload}
            className="btn btn-primary flex-1"
          >
            <Download className="w-4 h-4" />
            Download
          </button>
          <button
            onClick={handleDismiss}
            className="btn btn-ghost"
          >
            Skip
          </button>
        </div>
      </div>
    );
  }

  return null;
}

// Smaller inline update badge for status bar
export function UpdateBadge() {
  const [hasUpdate, setHasUpdate] = useState(false);
  const [version, setVersion] = useState(null);

  useEffect(() => {
    const checkUpdates = async () => {
      try {
        const result = await window.carful?.rpc?.invoke?.('update.check');
        if (result?.updateAvailable) {
          setHasUpdate(true);
          setVersion(result.version);
        }
      } catch (error) {
        // Silently fail
      }
    };

    const timeout = setTimeout(checkUpdates, 10000);
    return () => clearTimeout(timeout);
  }, []);

  if (!hasUpdate) return null;

  return (
    <div className="flex items-center gap-1 px-2 py-0.5 bg-carful-100 text-carful-700 rounded-full text-xs">
      <Sparkles className="w-3 h-3" />
      <span>v{version} available</span>
    </div>
  );
}

export default UpdateNotification;

import React, { useState, useCallback, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { useRPC } from '../hooks/useRPC';
import ErrorTable from './ErrorTable';
import ProgressBar from './ProgressBar';
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Play,
  Download,
  RefreshCw,
} from 'lucide-react';

function ValidationCard({ icon: Icon, label, value, variant = 'default' }) {
  const variants = {
    default: 'bg-slate-50 text-slate-600',
    success: 'bg-success-50 text-success-600',
    error: 'bg-error-50 text-error-600',
    warning: 'bg-warning-50 text-warning-600',
  };

  return (
    <div className={`p-6 rounded-xl ${variants[variant]}`}>
      <div className="flex items-center gap-3 mb-2">
        <Icon className="w-5 h-5" />
        <span className="text-sm font-medium">{label}</span>
      </div>
      <p className="text-3xl font-bold">{value.toLocaleString()}</p>
    </div>
  );
}

function ValidationResults() {
  const { state, actions } = useApp();
  const { invoke, loading } = useRPC();
  const { validation, dbPath, importFile, validating } = state;
  const [selectedError, setSelectedError] = useState(null);
  const [progress, setProgress] = useState(0);

  // Get the CSV path from the imported file
  const csvPath = importFile?.path;

  const handleValidate = useCallback(async () => {
    if (!dbPath && !csvPath) {
      actions.addLog('No data imported. Please import a CSV file first.');
      return;
    }

    actions.setValidating(true);
    setProgress(0);
    actions.addLog('Starting TIN validation...');

    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        setProgress((p) => Math.min(p + 15, 90));
      }, 150);

      // Use csv_path for validation (the Python backend validates directly from CSV)
      const result = await invoke('tin.validate', {
        csv_path: csvPath,
        db_path: dbPath,
      });

      clearInterval(progressInterval);
      setProgress(100);

      actions.setValidation({
        valid: result.valid || 0,
        invalid: result.invalid || 0,
        notin: result.notin || 0,
        errors: result.errors || [],
      });

      actions.addLog(
        `Validation complete: ${result.valid} valid, ${result.invalid} invalid, ${result.notin} NOTIN`
      );
    } catch (error) {
      actions.addLog(`Validation failed: ${error.message}`);
    } finally {
      actions.setValidating(false);
    }
  }, [dbPath, csvPath, invoke, actions]);

  // Auto-validate when data path changes
  useEffect(() => {
    if ((dbPath || csvPath) && validation.valid === 0 && validation.invalid === 0) {
      handleValidate();
    }
  }, [dbPath, csvPath]);

  const handleExportErrors = useCallback(() => {
    if (!validation.errors.length) return;

    // Create CSV content
    const headers = ['Row', 'TIN', 'Country', 'Error'];
    const rows = validation.errors.map((e) => [e.row, e.tin, e.country, e.message]);
    const csv = [headers, ...rows].map((r) => r.join(',')).join('\n');

    // Download CSV
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `validation_errors_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);

    actions.addLog(`Exported ${validation.errors.length} errors to CSV`);
  }, [validation.errors, actions]);

  const total = validation.valid + validation.invalid + validation.notin;

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Validation Results</h2>
          <p className="text-slate-500">TIN and data validation summary</p>
        </div>
        <div className="flex gap-2">
          {validation.errors.length > 0 && (
            <button onClick={handleExportErrors} className="btn btn-secondary">
              <Download className="w-4 h-4" />
              Export Errors
            </button>
          )}
          <button
            onClick={handleValidate}
            disabled={validating || (!dbPath && !csvPath)}
            className="btn btn-primary"
          >
            {validating ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            {validating ? 'Validating...' : 'Revalidate'}
          </button>
        </div>
      </header>

      {/* No data state */}
      {!dbPath && !csvPath && (
        <div className="card text-center py-12">
          <AlertTriangle className="w-12 h-12 text-warning-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-slate-900 mb-2">No Data Imported</h3>
          <p className="text-slate-500 mb-4">
            Please import a CSV file first to see validation results.
          </p>
          <button onClick={() => actions.setView('import')} className="btn btn-primary">
            Go to Import
          </button>
        </div>
      )}

      {/* Validating state */}
      {validating && (
        <div className="card">
          <h3 className="font-semibold text-slate-900 mb-4">Validating TINs...</h3>
          <ProgressBar progress={progress} message="Checking TIN formats and checksums..." />
        </div>
      )}

      {/* Results */}
      {(dbPath || csvPath) && !validating && total > 0 && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <ValidationCard
              icon={CheckCircle}
              label="Valid TINs"
              value={validation.valid}
              variant="success"
            />
            <ValidationCard
              icon={XCircle}
              label="Invalid TINs"
              value={validation.invalid}
              variant="error"
            />
            <ValidationCard
              icon={AlertTriangle}
              label="NOTIN (Missing)"
              value={validation.notin}
              variant="warning"
            />
          </div>

          {/* Validation rate */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-slate-900">Validation Rate</h3>
              <span className="text-2xl font-bold text-carful-600">
                {total > 0 ? ((validation.valid / total) * 100).toFixed(1) : 0}%
              </span>
            </div>
            <div className="h-4 bg-slate-200 rounded-full overflow-hidden flex">
              <div
                className="bg-success-500 transition-all"
                style={{ width: `${total > 0 ? (validation.valid / total) * 100 : 0}%` }}
              />
              <div
                className="bg-warning-500 transition-all"
                style={{ width: `${total > 0 ? (validation.notin / total) * 100 : 0}%` }}
              />
              <div
                className="bg-error-500 transition-all"
                style={{ width: `${total > 0 ? (validation.invalid / total) * 100 : 0}%` }}
              />
            </div>
            <div className="flex justify-between mt-2 text-xs text-slate-500">
              <span>Valid: {validation.valid}</span>
              <span>NOTIN: {validation.notin}</span>
              <span>Invalid: {validation.invalid}</span>
            </div>
          </div>

          {/* Error table */}
          {validation.errors.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-slate-900 mb-4">
                Validation Errors ({validation.errors.length})
              </h3>
              <ErrorTable
                errors={validation.errors}
                onSelectError={setSelectedError}
              />
            </div>
          )}

          {/* No errors state */}
          {validation.errors.length === 0 && validation.invalid === 0 && (
            <div className="card text-center py-8 bg-success-50 border-success-200">
              <CheckCircle className="w-12 h-12 text-success-600 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-success-900">
                All TINs Valid!
              </h3>
              <p className="text-success-700 mt-2">
                Your data is ready for CARF XML export.
              </p>
              <button
                onClick={() => actions.setView('export')}
                className="btn btn-success mt-4"
              >
                Proceed to Export
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default ValidationResults;

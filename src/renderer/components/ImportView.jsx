import React, { useState, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { useRPC } from '../hooks/useRPC';
import FileDropZone, { FilePreview } from './FileDropZone';
import ProgressBar from './ProgressBar';
import { FileSpreadsheet, Play, X, CheckCircle, AlertTriangle } from 'lucide-react';

function ImportView() {
  const { state, actions } = useApp();
  const { importCSV, previewCSV, loading } = useRPC();
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [progress, setProgress] = useState(0);

  const handleFileSelect = useCallback(
    async (file) => {
      setSelectedFile(file);
      setImportResult(null);
      setProgress(0);

      // Get file preview from Python backend
      try {
        const result = await previewCSV(file.path, 5);
        setPreview(result);
        actions.addLog(`Selected file: ${file.name}`);
      } catch (error) {
        console.error('Failed to preview CSV:', error);
        // Create a basic preview from file info
        setPreview({
          rows: [],
          headers: [],
          total_rows: 0,
        });
      }
    },
    [previewCSV, actions]
  );

  const handleRemoveFile = useCallback(() => {
    setSelectedFile(null);
    setPreview(null);
    setImportResult(null);
    setProgress(0);
  }, []);

  const handleImport = useCallback(async () => {
    if (!selectedFile) return;

    setImporting(true);
    setProgress(0);
    actions.addLog(`Starting import of ${selectedFile.name}...`);

    try {
      // Create a temp database path
      const paths = await window.carful?.app?.getPaths();
      const dbPath = paths?.temp
        ? `${paths.temp}/carful_import_${Date.now()}.db`
        : `/tmp/carful_import_${Date.now()}.db`;

      // Simulate progress updates
      const progressInterval = setInterval(() => {
        setProgress((p) => Math.min(p + 10, 90));
      }, 200);

      const result = await importCSV(selectedFile.path, dbPath);

      clearInterval(progressInterval);
      setProgress(100);

      setImportResult({
        success: true,
        rows: result.rows,
        errors: result.errors || [],
        dbPath: dbPath,
      });

      // Update global state
      actions.setDbPath(dbPath);
      actions.setImportFile(selectedFile);
      actions.setStats({ users: result.rows, transactions: result.rows });
      actions.addLog(`Import complete: ${result.rows} rows imported`);

      // Auto-navigate to validation after successful import
      setTimeout(() => {
        actions.setView('validation');
      }, 1500);
    } catch (error) {
      setImportResult({
        success: false,
        error: error.message,
      });
      actions.addLog(`Import failed: ${error.message}`);
    } finally {
      setImporting(false);
    }
  }, [selectedFile, importCSV, actions]);

  const handleBrowse = useCallback(async () => {
    try {
      const filePath = await window.carful?.dialog?.openCSV();
      if (filePath) {
        // Create a file-like object
        handleFileSelect({ path: filePath, name: filePath.split('/').pop(), size: 0 });
      }
    } catch (error) {
      console.error('Failed to open file dialog:', error);
    }
  }, [handleFileSelect]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <header>
        <h2 className="text-2xl font-bold text-slate-900">Import CSV</h2>
        <p className="text-slate-500">Import crypto transaction data from CSV files</p>
      </header>

      {/* File selection */}
      {!selectedFile && !importing && (
        <div className="card">
          <FileDropZone onFileSelect={handleFileSelect} accept=".csv" />
          <div className="mt-4 text-center">
            <button onClick={handleBrowse} className="btn btn-secondary">
              <FileSpreadsheet className="w-4 h-4" />
              Browse Files
            </button>
          </div>
        </div>
      )}

      {/* Selected file preview */}
      {selectedFile && !importing && !importResult && (
        <div className="card space-y-4">
          <FilePreview file={selectedFile} onRemove={handleRemoveFile} />

          {/* Preview table */}
          {preview?.headers?.length > 0 && (
            <div className="mt-4">
              <h4 className="font-medium text-slate-700 mb-2">Preview (first 5 rows)</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border border-slate-200 rounded-lg overflow-hidden">
                  <thead>
                    <tr className="bg-slate-50">
                      {preview.headers.map((header, idx) => (
                        <th
                          key={idx}
                          className="px-3 py-2 text-left font-medium text-slate-600 border-b"
                        >
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((row, rowIdx) => (
                      <tr key={rowIdx} className="hover:bg-slate-50">
                        {row.map((cell, cellIdx) => (
                          <td
                            key={cellIdx}
                            className="px-3 py-2 text-slate-700 border-b border-slate-100"
                          >
                            {cell}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {preview.total_rows > 0 && (
                <p className="text-sm text-slate-500 mt-2">
                  Total rows: {preview.total_rows.toLocaleString()}
                </p>
              )}
            </div>
          )}

          {/* Import button */}
          <div className="flex gap-3 pt-4 border-t border-slate-200">
            <button onClick={handleImport} className="btn btn-primary">
              <Play className="w-4 h-4" />
              Start Import
            </button>
            <button onClick={handleRemoveFile} className="btn btn-secondary">
              <X className="w-4 h-4" />
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Import progress */}
      {importing && (
        <div className="card">
          <h3 className="font-semibold text-slate-900 mb-4">Importing...</h3>
          <ProgressBar
            progress={progress}
            message={`Processing ${selectedFile?.name}...`}
            showTime
          />
        </div>
      )}

      {/* Import result */}
      {importResult && (
        <div
          className={`card ${
            importResult.success ? 'border-success-500' : 'border-error-500'
          }`}
        >
          <div className="flex items-start gap-4">
            {importResult.success ? (
              <div className="p-3 bg-success-50 rounded-full">
                <CheckCircle className="w-6 h-6 text-success-600" />
              </div>
            ) : (
              <div className="p-3 bg-error-50 rounded-full">
                <AlertTriangle className="w-6 h-6 text-error-600" />
              </div>
            )}
            <div className="flex-1">
              <h3 className="font-semibold text-slate-900">
                {importResult.success ? 'Import Successful' : 'Import Failed'}
              </h3>
              {importResult.success ? (
                <p className="text-slate-600 mt-1">
                  Successfully imported {importResult.rows.toLocaleString()} rows.
                  {importResult.errors.length > 0 &&
                    ` (${importResult.errors.length} warnings)`}
                </p>
              ) : (
                <p className="text-error-600 mt-1">{importResult.error}</p>
              )}
            </div>
          </div>

          {importResult.success && (
            <div className="mt-4 pt-4 border-t border-slate-200 flex gap-3">
              <button
                onClick={() => actions.setView('validation')}
                className="btn btn-primary"
              >
                View Validation Results
              </button>
              <button onClick={handleRemoveFile} className="btn btn-secondary">
                Import Another File
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ImportView;

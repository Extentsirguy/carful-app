import { useState, useCallback } from 'react';

/**
 * Hook for making RPC calls to the Python backend.
 * Uses the carful.rpc API exposed through the preload script.
 */
export function useRPC() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  /**
   * Make an RPC call to the Python backend.
   */
  const invoke = useCallback(async (method, params = {}) => {
    setLoading(true);
    setError(null);

    try {
      if (!window.carful?.rpc?.invoke) {
        throw new Error('RPC bridge not available');
      }
      const result = await window.carful.rpc.invoke(method, params);
      return result;
    } catch (err) {
      setError(err.message || 'RPC call failed');
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Convenience methods
  const getStats = useCallback(
    (dbPath) => invoke('db.stats', { db_path: dbPath }),
    [invoke]
  );

  const importCSV = useCallback(
    (csvPath, dbPath) => invoke('csv.import', { csv_path: csvPath, db_path: dbPath }),
    [invoke]
  );

  const previewCSV = useCallback(
    (csvPath, rows = 5) => invoke('csv.preview', { csv_path: csvPath, rows }),
    [invoke]
  );

  const validateTINs = useCallback(
    (dbPath) => invoke('tin.validate', { db_path: dbPath }),
    [invoke]
  );

  const validateSingleTIN = useCallback(
    (tin, country) => invoke('tin.validate_single', { tin, country }),
    [invoke]
  );

  const exportXML = useCallback(
    (dbPath, output, config) =>
      invoke('xml.export', { db_path: dbPath, output, config }),
    [invoke]
  );

  const healthCheck = useCallback(
    (csvPath) => invoke('health.check', { csv_path: csvPath }),
    [invoke]
  );

  const generatePDF = useCallback(
    (checkResult, output) => invoke('report.pdf', { check_result: checkResult, output }),
    [invoke]
  );

  const ping = useCallback(() => invoke('ping'), [invoke]);

  const getVersion = useCallback(() => invoke('version'), [invoke]);

  return {
    invoke,
    loading,
    error,
    // Convenience methods
    getStats,
    importCSV,
    previewCSV,
    validateTINs,
    validateSingleTIN,
    exportXML,
    healthCheck,
    generatePDF,
    ping,
    getVersion,
  };
}

export default useRPC;

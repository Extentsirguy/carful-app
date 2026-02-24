import React, { useState, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { useRPC } from '../hooks/useRPC';
import ProgressBar, { CircularProgress } from './ProgressBar';
import {
  HeartPulse,
  FileText,
  Download,
  AlertCircle,
  CheckCircle,
  AlertTriangle,
  Info,
  RefreshCw,
} from 'lucide-react';

function ScoreGauge({ score }) {
  const getColor = () => {
    if (score >= 90) return 'text-success-600';
    if (score >= 70) return 'text-warning-600';
    return 'text-error-600';
  };

  const getGrade = () => {
    if (score >= 90) return 'A';
    if (score >= 80) return 'B';
    if (score >= 70) return 'C';
    if (score >= 60) return 'D';
    return 'F';
  };

  const getLabel = () => {
    if (score >= 90) return 'Excellent';
    if (score >= 80) return 'Good';
    if (score >= 70) return 'Fair';
    if (score >= 60) return 'Poor';
    return 'Critical';
  };

  return (
    <div className="text-center">
      <div className="relative inline-block">
        <CircularProgress progress={score} size={120} strokeWidth={10} showLabel={false} />
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`text-3xl font-bold ${getColor()}`}>{getGrade()}</span>
        </div>
      </div>
      <p className="mt-2 text-lg font-medium text-slate-900">{score}%</p>
      <p className={`text-sm font-medium ${getColor()}`}>{getLabel()}</p>
    </div>
  );
}

function IssueCard({ icon: Icon, label, count, variant = 'default', items = [] }) {
  const [expanded, setExpanded] = useState(false);

  const variants = {
    error: { bg: 'bg-error-50', border: 'border-error-200', text: 'text-error-600' },
    warning: { bg: 'bg-warning-50', border: 'border-warning-200', text: 'text-warning-600' },
    info: { bg: 'bg-carful-50', border: 'border-carful-200', text: 'text-carful-600' },
    default: { bg: 'bg-slate-50', border: 'border-slate-200', text: 'text-slate-600' },
  };

  const style = variants[variant];

  return (
    <div className={`rounded-lg border ${style.border} overflow-hidden`}>
      <button
        onClick={() => items.length > 0 && setExpanded(!expanded)}
        className={`w-full p-4 ${style.bg} flex items-center justify-between`}
      >
        <div className="flex items-center gap-3">
          <Icon className={`w-5 h-5 ${style.text}`} />
          <span className="font-medium text-slate-900">{label}</span>
        </div>
        <span className={`text-2xl font-bold ${style.text}`}>{count}</span>
      </button>
      {expanded && items.length > 0 && (
        <div className="p-4 border-t border-slate-100 max-h-48 overflow-y-auto">
          <ul className="space-y-2 text-sm">
            {items.slice(0, 10).map((item, idx) => (
              <li key={idx} className="text-slate-600">
                {item}
              </li>
            ))}
            {items.length > 10 && (
              <li className="text-slate-400 italic">
                And {items.length - 10} more...
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

function HealthCheckView() {
  const { state, actions } = useApp();
  const { healthCheck, generatePDF } = useRPC();
  const { checkingHealth } = state;

  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [generatingPDF, setGeneratingPDF] = useState(false);

  const handleHealthCheck = useCallback(async () => {
    // Get CSV file from user
    const csvPath = await window.carful?.dialog?.openCSV();
    if (!csvPath) {
      actions.addLog('Health check cancelled - no file selected');
      return;
    }

    actions.setCheckingHealth(true);
    setProgress(0);
    setResult(null);
    actions.addLog(`Starting health check on ${csvPath.split('/').pop()}...`);

    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        setProgress((p) => Math.min(p + 8, 90));
      }, 200);

      const checkResult = await healthCheck(csvPath);

      clearInterval(progressInterval);
      setProgress(100);

      setResult(checkResult);
      actions.setHealthCheck(checkResult);
      actions.addLog(`Health check complete. Score: ${checkResult.score}%`);
    } catch (error) {
      actions.addLog(`Health check failed: ${error.message}`);
      setResult({ error: error.message });
    } finally {
      actions.setCheckingHealth(false);
    }
  }, [healthCheck, actions]);

  const handleDownloadPDF = useCallback(async () => {
    if (!result || result.error) return;

    const outputPath = await window.carful?.dialog?.savePDF(
      `health_check_${Date.now()}.pdf`
    );

    if (!outputPath) {
      actions.addLog('PDF download cancelled');
      return;
    }

    setGeneratingPDF(true);
    actions.addLog('Generating PDF report...');

    try {
      await generatePDF(result, outputPath);
      actions.addLog(`PDF report saved to ${outputPath}`);
    } catch (error) {
      actions.addLog(`PDF generation failed: ${error.message}`);
    } finally {
      setGeneratingPDF(false);
    }
  }, [result, generatePDF, actions]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <header>
        <h2 className="text-2xl font-bold text-slate-900">Data Health Check</h2>
        <p className="text-slate-500">
          Free compliance assessment report for your crypto transaction data
        </p>
      </header>

      {/* Info card */}
      {!result && !checkingHealth && (
        <div className="card bg-gradient-to-br from-purple-50 to-carful-50 border-carful-200">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-white rounded-xl shadow-sm">
              <HeartPulse className="w-8 h-8 text-carful-600" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-slate-900">
                What's included in the Health Check?
              </h3>
              <ul className="mt-3 space-y-2 text-slate-600">
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-success-600" />
                  TIN validation across all jurisdictions
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-success-600" />
                  CARF transaction code mapping verification
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-success-600" />
                  Data quality and completeness analysis
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-success-600" />
                  Compliance score and recommendations
                </li>
              </ul>
            </div>
          </div>

          <button onClick={handleHealthCheck} className="btn btn-primary mt-6 w-full">
            <HeartPulse className="w-5 h-5" />
            Run Health Check
          </button>
        </div>
      )}

      {/* Progress */}
      {checkingHealth && (
        <div className="card">
          <h3 className="font-semibold text-slate-900 mb-4">Analyzing your data...</h3>
          <ProgressBar
            progress={progress}
            message="Checking TINs, transaction codes, and data quality..."
            showTime
          />
        </div>
      )}

      {/* Results */}
      {result && !result.error && (
        <>
          {/* Score card */}
          <div className="card">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
              <ScoreGauge score={result.score || 0} />

              <div className="md:col-span-2">
                <h3 className="text-lg font-semibold text-slate-900 mb-2">
                  Compliance Score
                </h3>
                <p className="text-slate-600 mb-4">
                  {result.score >= 90
                    ? "Your data is in excellent shape and ready for CARF filing."
                    : result.score >= 70
                    ? "Your data has some issues that should be addressed before filing."
                    : "Significant issues found. Review the details below to improve compliance."}
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={handleDownloadPDF}
                    disabled={generatingPDF}
                    className="btn btn-primary"
                  >
                    {generatingPDF ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <FileText className="w-4 h-4" />
                    )}
                    Download PDF Report
                  </button>
                  <button onClick={handleHealthCheck} className="btn btn-secondary">
                    <RefreshCw className="w-4 h-4" />
                    Check Another File
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Issue summary */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <IssueCard
              icon={AlertCircle}
              label="Critical Issues"
              count={result.errors?.length || 0}
              variant="error"
              items={result.errors?.map((e) => e.message) || []}
            />
            <IssueCard
              icon={AlertTriangle}
              label="Warnings"
              count={result.warnings?.length || 0}
              variant="warning"
              items={result.warnings?.map((w) => w.message) || []}
            />
            <IssueCard
              icon={Info}
              label="Suggestions"
              count={result.suggestions?.length || 0}
              variant="info"
              items={result.suggestions || []}
            />
          </div>

          {/* Data overview */}
          <div className="card">
            <h3 className="font-semibold text-slate-900 mb-4">Data Overview</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-slate-50 rounded-lg text-center">
                <p className="text-2xl font-bold text-slate-900">
                  {(result.summary?.total_records || 0).toLocaleString()}
                </p>
                <p className="text-sm text-slate-500">Total Records</p>
              </div>
              <div className="p-4 bg-slate-50 rounded-lg text-center">
                <p className="text-2xl font-bold text-slate-900">
                  {(result.summary?.unique_users || 0).toLocaleString()}
                </p>
                <p className="text-sm text-slate-500">Unique Users</p>
              </div>
              <div className="p-4 bg-slate-50 rounded-lg text-center">
                <p className="text-2xl font-bold text-slate-900">
                  {result.summary?.valid_tins || 0}%
                </p>
                <p className="text-sm text-slate-500">Valid TINs</p>
              </div>
              <div className="p-4 bg-slate-50 rounded-lg text-center">
                <p className="text-2xl font-bold text-slate-900">
                  {result.summary?.mapped_codes || 0}%
                </p>
                <p className="text-sm text-slate-500">Mapped Codes</p>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Error state */}
      {result?.error && (
        <div className="card bg-error-50 border-error-200">
          <div className="flex items-start gap-4">
            <AlertCircle className="w-6 h-6 text-error-600 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-error-900">Health Check Failed</h3>
              <p className="text-error-700 mt-1">{result.error}</p>
              <button onClick={handleHealthCheck} className="btn btn-secondary mt-4">
                Try Again
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default HealthCheckView;

import React, { useEffect } from 'react';
import { X, FileText, Code, ExternalLink } from 'lucide-react';

function ErrorDetail({ error, csvRowData, isOpen, onClose }) {
  // Close on Escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen, onClose]);

  if (!isOpen || !error) {
    return null;
  }

  // Generate the corrected TIN XML element preview
  const xmlPreview = `<TaxIdentificationNumber>
  <Value>${error.tin || 'TBD'}</Value>
  <Country>${error.country || 'TBD'}</Country>
</TaxIdentificationNumber>`;

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 z-40 transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 overflow-y-auto">
        <div className="flex items-center justify-center min-h-screen px-4">
          <div
            className="bg-white rounded-lg shadow-xl max-w-2xl w-full transform transition-all"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50">
              <h2 className="text-lg font-semibold text-slate-900">
                Error Details
              </h2>
              <button
                onClick={onClose}
                className="p-1 hover:bg-slate-200 rounded transition-colors text-slate-400 hover:text-slate-600"
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="px-6 py-6 space-y-6 max-h-[calc(100vh-200px)] overflow-y-auto">
              {/* Error Context Section */}
              <section>
                <h3 className="text-sm font-semibold text-slate-700 mb-3 uppercase tracking-wide">
                  Error Context
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-50 p-3 rounded border border-slate-200">
                    <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">
                      Row Number
                    </p>
                    <p className="text-sm font-mono text-slate-900">
                      {error.row}
                    </p>
                  </div>
                  <div className="bg-slate-50 p-3 rounded border border-slate-200">
                    <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">
                      Country
                    </p>
                    <p className="text-sm font-mono text-slate-900">
                      {error.country || '—'}
                    </p>
                  </div>
                  <div className="col-span-2 bg-slate-50 p-3 rounded border border-slate-200">
                    <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">
                      TIN
                    </p>
                    <p className="text-sm font-mono text-slate-900">
                      {error.tin || '—'}
                    </p>
                  </div>
                </div>
              </section>

              {/* Error Message Section */}
              <section>
                <h3 className="text-sm font-semibold text-slate-700 mb-3 uppercase tracking-wide">
                  Full Error Message
                </h3>
                <div className="bg-red-50 border border-red-200 rounded p-4">
                  <p className="text-sm text-red-800 leading-relaxed">
                    {error.message}
                  </p>
                </div>
              </section>

              {/* Original CSV Row Data Section */}
              {csvRowData && (
                <section>
                  <div className="flex items-center gap-2 mb-3">
                    <FileText className="w-4 h-4 text-slate-600" />
                    <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
                      Original CSV Row Data
                    </h3>
                  </div>
                  <div className="bg-slate-50 border border-slate-200 rounded overflow-x-auto">
                    <pre className="text-xs text-slate-700 p-4 font-mono whitespace-pre-wrap break-words">
                      {JSON.stringify(csvRowData, null, 2)}
                    </pre>
                  </div>
                </section>
              )}

              {/* Expected XML Element Section */}
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <Code className="w-4 h-4 text-slate-600" />
                  <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
                    Expected XML Element
                  </h3>
                </div>
                <div className="bg-slate-900 rounded overflow-x-auto">
                  <pre className="text-xs text-green-400 p-4 font-mono">
                    {xmlPreview}
                  </pre>
                </div>
              </section>

              {/* OECD CARF Documentation Link */}
              <section>
                <a
                  href="https://www.oecd.org/en/topics/crypto-asset-reporting-framework.html"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-blue-50 border border-blue-200 rounded hover:bg-blue-100 transition-colors group"
                >
                  <span className="text-sm font-medium text-blue-700">
                    View OECD CARF Documentation
                  </span>
                  <ExternalLink className="w-4 h-4 text-blue-600 group-hover:text-blue-800" />
                </a>
              </section>
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-200 bg-slate-50">
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded hover:bg-slate-50 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

export default ErrorDetail;

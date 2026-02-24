import React, { useState } from 'react';
import { Shield, X } from 'lucide-react';

function UpgradePrompt({ isOpen, onDismiss, onEnterLicense, onViewPlans }) {
  const [dismissed, setDismissed] = useState(false);

  if (!isOpen || dismissed) {
    return null;
  }

  const handleDismiss = () => {
    setDismissed(true);
    if (onDismiss) {
      onDismiss();
    }
  };

  const handleEnterLicense = () => {
    setDismissed(true);
    if (onEnterLicense) {
      onEnterLicense();
    }
  };

  const handleViewPlans = () => {
    setDismissed(true);
    window.open('https://carful.app/#pricing', '_blank');
    if (onViewPlans) {
      onViewPlans();
    }
  };

  return (
    <>
      {/* Blur backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
        onClick={handleDismiss}
      />

      {/* Modal */}
      <div className="fixed inset-0 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-8 relative">
          {/* Close button */}
          <button
            onClick={handleDismiss}
            className="absolute top-4 right-4 p-1 hover:bg-slate-100 rounded-lg transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>

          {/* Shield icon */}
          <div className="flex justify-center mb-4">
            <div className="w-16 h-16 bg-carful-100 rounded-full flex items-center justify-center">
              <Shield className="w-8 h-8 text-carful-600" />
            </div>
          </div>

          {/* Title */}
          <h2 className="text-2xl font-bold text-center text-slate-900 mb-2">
            Upgrade to CARFul Pro
          </h2>

          {/* Subtitle */}
          <p className="text-center text-slate-600 mb-6">
            XML export requires an active Pro subscription
          </p>

          {/* Features list */}
          <div className="space-y-3 mb-8">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 mt-0.5">
                <div className="w-5 h-5 rounded-full bg-carful-100 flex items-center justify-center">
                  <span className="text-carful-600 text-sm font-bold">✓</span>
                </div>
              </div>
              <p className="text-sm text-slate-700">XML export with full CARF compliance</p>
            </div>

            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 mt-0.5">
                <div className="w-5 h-5 rounded-full bg-carful-100 flex items-center justify-center">
                  <span className="text-carful-600 text-sm font-bold">✓</span>
                </div>
              </div>
              <p className="text-sm text-slate-700">Auto-correction of common errors</p>
            </div>

            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 mt-0.5">
                <div className="w-5 h-5 rounded-full bg-carful-100 flex items-center justify-center">
                  <span className="text-carful-600 text-sm font-bold">✓</span>
                </div>
              </div>
              <p className="text-sm text-slate-700">Regular schema and standard updates</p>
            </div>

            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 mt-0.5">
                <div className="w-5 h-5 rounded-full bg-carful-100 flex items-center justify-center">
                  <span className="text-carful-600 text-sm font-bold">✓</span>
                </div>
              </div>
              <p className="text-sm text-slate-700">Process unlimited files</p>
            </div>

            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 mt-0.5">
                <div className="w-5 h-5 rounded-full bg-carful-100 flex items-center justify-center">
                  <span className="text-carful-600 text-sm font-bold">✓</span>
                </div>
              </div>
              <p className="text-sm text-slate-700">Priority support</p>
            </div>
          </div>

          {/* Buttons */}
          <div className="space-y-3">
            <button
              onClick={handleViewPlans}
              className="btn btn-primary w-full"
            >
              View Plans
            </button>

            <button
              onClick={handleEnterLicense}
              className="btn btn-secondary w-full"
            >
              Enter License Key
            </button>

            <button
              onClick={handleDismiss}
              className="btn btn-outline w-full"
            >
              Continue with Health Check
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

export default UpgradePrompt;

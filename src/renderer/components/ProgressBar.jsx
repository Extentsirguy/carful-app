import React, { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';

function ProgressBar({
  progress = 0,
  message = '',
  showPercentage = true,
  showTime = true,
  variant = 'default',
  animated = true,
}) {
  const [startTime] = useState(Date.now());
  const [elapsed, setElapsed] = useState(0);

  // Update elapsed time
  useEffect(() => {
    if (progress > 0 && progress < 100 && showTime) {
      const interval = setInterval(() => {
        setElapsed(Date.now() - startTime);
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [progress, startTime, showTime]);

  // Calculate estimated remaining time
  const estimatedRemaining = progress > 0 ? (elapsed / progress) * (100 - progress) : 0;

  // Format time display
  const formatTime = (ms) => {
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  // Variant styles
  const variants = {
    default: {
      bg: 'bg-slate-200',
      fill: 'bg-carful-500',
    },
    success: {
      bg: 'bg-success-100',
      fill: 'bg-success-500',
    },
    warning: {
      bg: 'bg-warning-100',
      fill: 'bg-warning-500',
    },
    error: {
      bg: 'bg-error-100',
      fill: 'bg-error-500',
    },
  };

  const style = variants[variant] || variants.default;

  return (
    <div className="space-y-2">
      {/* Message */}
      {message && (
        <div className="flex items-center gap-2 text-sm text-slate-600">
          {animated && progress < 100 && (
            <Loader2 className="w-4 h-4 animate-spin text-carful-500" />
          )}
          <span>{message}</span>
        </div>
      )}

      {/* Progress bar container */}
      <div className={`h-3 rounded-full overflow-hidden ${style.bg}`}>
        <div
          className={`h-full rounded-full transition-all duration-300 ${style.fill} ${
            animated && progress < 100 ? 'animate-pulse' : ''
          }`}
          style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
        />
      </div>

      {/* Progress info */}
      <div className="flex justify-between text-xs text-slate-500">
        <span>
          {showPercentage && `${Math.round(progress)}%`}
          {showTime && elapsed > 0 && ` • Elapsed: ${formatTime(elapsed)}`}
        </span>
        {showTime && progress > 0 && progress < 100 && (
          <span>Est. remaining: {formatTime(estimatedRemaining)}</span>
        )}
      </div>
    </div>
  );
}

// Compact progress indicator
export function ProgressIndicator({ progress, size = 'md' }) {
  const sizes = {
    sm: 'h-1',
    md: 'h-2',
    lg: 'h-3',
  };

  return (
    <div className={`w-full rounded-full overflow-hidden bg-slate-200 ${sizes[size]}`}>
      <div
        className="h-full rounded-full bg-carful-500 transition-all duration-300"
        style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
      />
    </div>
  );
}

// Circular progress indicator
export function CircularProgress({ progress, size = 60, strokeWidth = 6, showLabel = true }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (progress / 100) * circumference;

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="-rotate-90">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          className="stroke-slate-200 fill-none"
        />
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="stroke-carful-500 fill-none transition-all duration-300"
        />
      </svg>
      {showLabel && (
        <span className="absolute text-sm font-medium text-slate-700">
          {Math.round(progress)}%
        </span>
      )}
    </div>
  );
}

export default ProgressBar;

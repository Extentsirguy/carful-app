import React from 'react';
import { useApp } from '../context/AppContext';
import { ChevronRight, ChevronLeft, Activity, Trash2 } from 'lucide-react';

function ActivityPanel({ isOpen, onToggle }) {
  const { state } = useApp();
  const { activityLog } = state;

  const formatTime = (date) => {
    return new Date(date).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  // Determine log entry type for styling
  const getEntryStyle = (message) => {
    if (message.toLowerCase().includes('error') || message.toLowerCase().includes('failed')) {
      return 'border-l-error-500 bg-error-50';
    }
    if (message.toLowerCase().includes('warning')) {
      return 'border-l-warning-500 bg-warning-50';
    }
    if (message.toLowerCase().includes('complete') || message.toLowerCase().includes('success')) {
      return 'border-l-success-500 bg-success-50';
    }
    return 'border-l-slate-300 bg-slate-50';
  };

  return (
    <aside
      className={`
        bg-white border-l border-slate-200 flex flex-col
        transition-all duration-300 ease-in-out
        ${isOpen ? 'w-80' : 'w-12'}
      `}
    >
      {/* Header */}
      <div className="p-3 border-b border-slate-200 flex items-center justify-between">
        {isOpen && (
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-slate-500" />
            <h3 className="font-medium text-slate-700">Activity Log</h3>
          </div>
        )}
        <button
          onClick={onToggle}
          className="p-1.5 hover:bg-slate-100 rounded-md transition-colors"
          title={isOpen ? 'Collapse panel' : 'Expand panel'}
        >
          {isOpen ? (
            <ChevronRight className="w-4 h-4 text-slate-500" />
          ) : (
            <ChevronLeft className="w-4 h-4 text-slate-500" />
          )}
        </button>
      </div>

      {/* Content */}
      {isOpen && (
        <div className="flex-1 overflow-y-auto p-3">
          {activityLog.length === 0 ? (
            <div className="text-center py-8 text-slate-400">
              <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No activity yet</p>
            </div>
          ) : (
            <div className="space-y-2">
              {activityLog.map((entry, idx) => (
                <div
                  key={idx}
                  className={`
                    p-2.5 rounded-r-lg border-l-2 text-sm
                    ${getEntryStyle(entry.message)}
                  `}
                >
                  <p className="text-slate-700">{entry.message}</p>
                  <p className="text-xs text-slate-400 mt-1">
                    {formatTime(entry.time)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Collapsed state icons */}
      {!isOpen && (
        <div className="flex-1 flex flex-col items-center pt-4 gap-3">
          <div className="relative">
            <Activity className="w-5 h-5 text-slate-400" />
            {activityLog.length > 0 && (
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-carful-500 rounded-full text-white text-[8px] flex items-center justify-center">
                {activityLog.length > 9 ? '9+' : activityLog.length}
              </span>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}

export default ActivityPanel;

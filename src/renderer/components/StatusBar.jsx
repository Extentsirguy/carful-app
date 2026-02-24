import React, { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { Database, Clock, Shield } from 'lucide-react';

function StatusBar() {
  const { state } = useApp();
  const { dbPath, stats, lastExport } = state;
  const [version, setVersion] = useState('1.0.0');
  const [currentTime, setCurrentTime] = useState(new Date());

  // Get app version on mount
  useEffect(() => {
    async function getVersion() {
      try {
        const v = await window.carful?.app?.getVersion();
        if (v) setVersion(v);
      } catch (error) {
        console.error('Failed to get version:', error);
      }
    }
    getVersion();
  }, []);

  // Update clock every minute
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(new Date());
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const formatDate = (date) => {
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  return (
    <footer className="h-8 bg-slate-100 border-t border-slate-200 px-4 flex items-center justify-between text-xs text-slate-500">
      {/* Left section */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <Database className="w-3.5 h-3.5" />
          <span>
            {dbPath
              ? `${stats.users.toLocaleString()} users • ${stats.transactions.toLocaleString()} transactions`
              : 'No data loaded'}
          </span>
        </div>

        {lastExport && (
          <div className="flex items-center gap-1.5">
            <span className="text-slate-300">|</span>
            <span>
              Last export: {new Date(lastExport.timestamp || Date.now()).toLocaleString()}
            </span>
          </div>
        )}
      </div>

      {/* Right section */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <Shield className="w-3.5 h-3.5 text-success-600" />
          <span className="text-success-600">Local Processing</span>
        </div>

        <div className="flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5" />
          <span>
            {formatDate(currentTime)} {formatTime(currentTime)}
          </span>
        </div>

        <span className="text-slate-400">v{version}</span>
      </div>
    </footer>
  );
}

export default StatusBar;

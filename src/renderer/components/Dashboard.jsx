import React from 'react';
import { useApp } from '../context/AppContext';
import {
  FileText,
  Users,
  ArrowRightLeft,
  CheckCircle,
  Upload,
  Download,
  HeartPulse,
} from 'lucide-react';

function StatCard({ icon: Icon, label, value, color = 'carful' }) {
  const colorClasses = {
    carful: 'bg-carful-50 text-carful-600',
    success: 'bg-success-50 text-success-600',
    warning: 'bg-warning-50 text-warning-600',
    error: 'bg-error-50 text-error-600',
  };

  return (
    <div className="card flex items-center gap-4">
      <div className={`p-3 rounded-xl ${colorClasses[color]}`}>
        <Icon className="w-6 h-6" />
      </div>
      <div>
        <p className="text-2xl font-bold text-slate-900">{value.toLocaleString()}</p>
        <p className="text-sm text-slate-500">{label}</p>
      </div>
    </div>
  );
}

function QuickActionButton({ icon: Icon, label, onClick, variant = 'primary' }) {
  const variants = {
    primary: 'btn-primary',
    secondary: 'btn-secondary',
    accent: 'bg-purple-600 text-white hover:bg-purple-700 focus:ring-purple-500',
  };

  return (
    <button onClick={onClick} className={`btn ${variants[variant]} py-3 px-5`}>
      <Icon className="w-5 h-5" />
      {label}
    </button>
  );
}

function Dashboard() {
  const { state, actions } = useApp();
  const { stats, validation, lastExport } = state;

  return (
    <div className="space-y-6">
      {/* Header */}
      <header>
        <h2 className="text-2xl font-bold text-slate-900">Dashboard</h2>
        <p className="text-slate-500">CARF XML Generation Overview</p>
      </header>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={FileText} label="Files Imported" value={stats.users > 0 ? 1 : 0} />
        <StatCard icon={Users} label="Users" value={stats.users} color="carful" />
        <StatCard
          icon={ArrowRightLeft}
          label="Transactions"
          value={stats.transactions}
          color="carful"
        />
        <StatCard
          icon={CheckCircle}
          label="Valid TINs"
          value={validation.valid}
          color="success"
        />
      </div>

      {/* Quick Actions */}
      <div className="card">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Quick Actions</h3>
        <div className="flex flex-wrap gap-3">
          <QuickActionButton
            icon={Upload}
            label="Import CSV"
            onClick={() => actions.setView('import')}
            variant="primary"
          />
          <QuickActionButton
            icon={Download}
            label="Export XML"
            onClick={() => actions.setView('export')}
            variant="secondary"
          />
          <QuickActionButton
            icon={HeartPulse}
            label="Health Check"
            onClick={() => actions.setView('health-check')}
            variant="accent"
          />
        </div>
      </div>

      {/* Last Export Info */}
      {lastExport && (
        <div className="card">
          <h3 className="text-lg font-semibold text-slate-900 mb-3">Last Export</h3>
          <div className="flex items-center gap-4 text-sm text-slate-600">
            <span>
              <strong>File:</strong> {lastExport.file}
            </span>
            <span>
              <strong>Size:</strong> {(lastExport.size / 1024).toFixed(1)} KB
            </span>
            <span>
              <strong>Duration:</strong> {lastExport.duration.toFixed(2)}s
            </span>
          </div>
        </div>
      )}

      {/* Getting Started (shown when no data) */}
      {stats.users === 0 && (
        <div className="card bg-gradient-to-br from-carful-50 to-carful-100 border-carful-200">
          <h3 className="text-lg font-semibold text-carful-900 mb-2">Getting Started</h3>
          <p className="text-carful-700 mb-4">
            Welcome to CARFul! To begin generating CARF-compliant XML files:
          </p>
          <ol className="list-decimal list-inside space-y-2 text-carful-700">
            <li>Configure your RCASP details in Settings</li>
            <li>Import your crypto transaction CSV file</li>
            <li>Review validation results and fix any TIN errors</li>
            <li>Export your CARF XML file</li>
          </ol>
          <button
            onClick={() => actions.setView('settings')}
            className="btn btn-primary mt-4"
          >
            Configure Settings
          </button>
        </div>
      )}
    </div>
  );
}

export default Dashboard;

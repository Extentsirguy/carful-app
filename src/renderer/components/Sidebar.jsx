import React from 'react';
import { useApp } from '../context/AppContext';
import {
  LayoutDashboard,
  Upload,
  CheckCircle,
  Download,
  HeartPulse,
  Settings,
  Check,
  Lock,
} from 'lucide-react';

const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'import', label: 'Import', icon: Upload },
  { id: 'validation', label: 'Validation', icon: CheckCircle },
  { id: 'export', label: 'Export', icon: Download },
  { id: 'health-check', label: 'Health Check', icon: HeartPulse },
  { id: 'settings', label: 'Settings', icon: Settings },
];

function Sidebar() {
  const { state, actions, isPro } = useApp();
  const { currentView } = state;

  return (
    <aside className="w-56 bg-slate-900 text-white flex flex-col">
      {/* Logo */}
      <div className="p-4 border-b border-slate-800">
        <h1 className="text-xl font-bold text-carful-400">CARFul</h1>
        <span className="text-xs text-slate-500">CARF Compliance Tool</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentView === item.id;
            const isExport = item.id === 'export';

            return (
              <li key={item.id}>
                <button
                  onClick={() => actions.setView(item.id)}
                  className={`
                    w-full flex items-center gap-3 px-3 py-2.5 rounded-lg
                    transition-all duration-200 text-left
                    ${
                      isActive
                        ? 'bg-carful-600 text-white'
                        : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                    }
                  `}
                >
                  <Icon className="w-5 h-5" />
                  <span className="font-medium">{item.label}</span>
                  {isExport && (
                    <span className="ml-auto flex-shrink-0">
                      {isPro ? (
                        <Check className="w-4 h-4 text-carful-400" />
                      ) : (
                        <Lock className="w-4 h-4 text-slate-500" />
                      )}
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-slate-800">
        <div className="text-xs text-slate-500">
          <p>© 2025 CARFul</p>
          <p className="mt-1">All data processed locally</p>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;

import React, { useEffect } from 'react';
import { AppProvider, useApp } from './context/AppContext';
import ErrorBoundary from './components/ErrorBoundary';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import ImportView from './components/ImportView';
import ValidationResults from './components/ValidationResults';
import ExportView from './components/ExportView';
import HealthCheckView from './components/HealthCheckView';
import SettingsPanel from './components/SettingsPanel';
import StatusBar from './components/StatusBar';
import UpdateNotification from './components/UpdateNotification';

// View components mapping
const views = {
  dashboard: Dashboard,
  import: ImportView,
  validation: ValidationResults,
  export: ExportView,
  'health-check': HealthCheckView,
  settings: SettingsPanel,
};

function AppContent() {
  const { state, actions } = useApp();
  const { currentView } = state;

  // Get current view component
  const ViewComponent = views[currentView] || Dashboard;

  // Initialize app on mount
  useEffect(() => {
    async function init() {
      // Get app version
      try {
        const version = await window.carful?.app?.getVersion();
        if (version) {
          actions.addLog(`CARFul v${version} initialized`);
        }
      } catch (error) {
        console.error('Failed to get app version:', error);
      }

      // Load saved settings
      try {
        const settings = await window.carful?.settings?.getAll();
        if (settings) {
          actions.setSettings(settings);
        }
      } catch (error) {
        console.error('Failed to load settings:', error);
      }

      // Load saved license
      try {
        const license = await window.carful?.license?.get();
        if (license && license.key) {
          actions.setLicense(license);
        }
      } catch (error) {
        console.error('Failed to load license:', error);
      }

      actions.addLog('Welcome to CARFul - CARF Compliance Tool');
    }

    init();
  }, [actions]);

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {/* Sidebar Navigation */}
      <Sidebar />

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          <ViewComponent />
        </div>

        {/* Status Bar */}
        <StatusBar />
      </main>

      {/* Update Notification */}
      <UpdateNotification />
    </div>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <AppProvider>
        <AppContent />
      </AppProvider>
    </ErrorBoundary>
  );
}

export default App;

import React, { createContext, useContext, useReducer, useCallback, useMemo } from 'react';

// Initial state
const initialState = {
  // Current view
  currentView: 'dashboard',

  // Database state
  dbPath: null,
  stats: {
    users: 0,
    transactions: 0,
  },

  // Import state
  importFile: null,
  importing: false,
  importProgress: 0,

  // Validation state
  validation: {
    valid: 0,
    invalid: 0,
    notin: 0,
    errors: [],
  },
  validating: false,

  // Export state
  exporting: false,
  exportProgress: 0,
  lastExport: null,

  // Health check state
  healthCheck: null,
  checkingHealth: false,

  // License state
  license: {
    key: null,
    email: null,
    status: 'free',
    expiresAt: null,
    machineId: null,
  },

  // Settings
  settings: {
    rcasp: {
      name: '',
      tin: '',
      country: 'US',
      city: '',
      street: '',
    },
    export: {
      sendingCountry: 'US',
      receivingCountry: 'GB',
      reportingYear: new Date().getFullYear(),
      messageType: 'CARF1',
    },
    advanced: {
      validationStrictness: 'strict',
      autoUpdate: true,
      debugMode: false,
    },
  },

  // UI state
  rightPanelOpen: true,
  activityLog: [],
  notifications: [],
};

// Action types
const ActionTypes = {
  SET_VIEW: 'SET_VIEW',
  SET_DB_PATH: 'SET_DB_PATH',
  SET_STATS: 'SET_STATS',
  SET_IMPORT_FILE: 'SET_IMPORT_FILE',
  SET_IMPORTING: 'SET_IMPORTING',
  SET_IMPORT_PROGRESS: 'SET_IMPORT_PROGRESS',
  SET_VALIDATION: 'SET_VALIDATION',
  SET_VALIDATING: 'SET_VALIDATING',
  SET_EXPORTING: 'SET_EXPORTING',
  SET_EXPORT_PROGRESS: 'SET_EXPORT_PROGRESS',
  SET_LAST_EXPORT: 'SET_LAST_EXPORT',
  SET_HEALTH_CHECK: 'SET_HEALTH_CHECK',
  SET_CHECKING_HEALTH: 'SET_CHECKING_HEALTH',
  SET_LICENSE: 'SET_LICENSE',
  CLEAR_LICENSE: 'CLEAR_LICENSE',
  SET_SETTINGS: 'SET_SETTINGS',
  UPDATE_RCASP: 'UPDATE_RCASP',
  UPDATE_EXPORT_OPTIONS: 'UPDATE_EXPORT_OPTIONS',
  UPDATE_ADVANCED: 'UPDATE_ADVANCED',
  TOGGLE_RIGHT_PANEL: 'TOGGLE_RIGHT_PANEL',
  ADD_LOG: 'ADD_LOG',
  ADD_NOTIFICATION: 'ADD_NOTIFICATION',
  DISMISS_NOTIFICATION: 'DISMISS_NOTIFICATION',
  RESET_STATE: 'RESET_STATE',
};

// Reducer
function appReducer(state, action) {
  switch (action.type) {
    case ActionTypes.SET_VIEW:
      return { ...state, currentView: action.payload };

    case ActionTypes.SET_DB_PATH:
      return { ...state, dbPath: action.payload };

    case ActionTypes.SET_STATS:
      return { ...state, stats: action.payload };

    case ActionTypes.SET_IMPORT_FILE:
      return { ...state, importFile: action.payload };

    case ActionTypes.SET_IMPORTING:
      return { ...state, importing: action.payload };

    case ActionTypes.SET_IMPORT_PROGRESS:
      return { ...state, importProgress: action.payload };

    case ActionTypes.SET_VALIDATION:
      return { ...state, validation: action.payload };

    case ActionTypes.SET_VALIDATING:
      return { ...state, validating: action.payload };

    case ActionTypes.SET_EXPORTING:
      return { ...state, exporting: action.payload };

    case ActionTypes.SET_EXPORT_PROGRESS:
      return { ...state, exportProgress: action.payload };

    case ActionTypes.SET_LAST_EXPORT:
      return { ...state, lastExport: action.payload };

    case ActionTypes.SET_HEALTH_CHECK:
      return { ...state, healthCheck: action.payload };

    case ActionTypes.SET_CHECKING_HEALTH:
      return { ...state, checkingHealth: action.payload };

    case ActionTypes.SET_LICENSE:
      return { ...state, license: action.payload };

    case ActionTypes.CLEAR_LICENSE:
      return { ...state, license: { key: null, email: null, status: 'free', expiresAt: null, machineId: null } };

    case ActionTypes.SET_SETTINGS:
      return { ...state, settings: action.payload };

    case ActionTypes.UPDATE_RCASP:
      return {
        ...state,
        settings: {
          ...state.settings,
          rcasp: { ...state.settings.rcasp, ...action.payload },
        },
      };

    case ActionTypes.UPDATE_EXPORT_OPTIONS:
      return {
        ...state,
        settings: {
          ...state.settings,
          export: { ...state.settings.export, ...action.payload },
        },
      };

    case ActionTypes.UPDATE_ADVANCED:
      return {
        ...state,
        settings: {
          ...state.settings,
          advanced: { ...state.settings.advanced, ...action.payload },
        },
      };

    case ActionTypes.TOGGLE_RIGHT_PANEL:
      return { ...state, rightPanelOpen: !state.rightPanelOpen };

    case ActionTypes.ADD_LOG:
      return {
        ...state,
        activityLog: [
          { time: new Date(), message: action.payload },
          ...state.activityLog.slice(0, 99),
        ],
      };

    case ActionTypes.ADD_NOTIFICATION:
      return {
        ...state,
        notifications: [...state.notifications, { id: Date.now(), ...action.payload }],
      };

    case ActionTypes.DISMISS_NOTIFICATION:
      return {
        ...state,
        notifications: state.notifications.filter((n) => n.id !== action.payload),
      };

    case ActionTypes.RESET_STATE:
      return initialState;

    default:
      return state;
  }
}

// Create context
const AppContext = createContext(null);

// Provider component
export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  // Load license from electron-store on mount
  React.useEffect(() => {
    async function loadLicense() {
      try {
        const licenseData = await window.carful?.license?.get();
        if (licenseData) {
          dispatch({ type: ActionTypes.SET_LICENSE, payload: licenseData });
        }
      } catch (error) {
        console.error('Failed to load license:', error);
      }
    }
    loadLicense();
  }, []);

  // Action creators
  const setView = useCallback((view) => {
    dispatch({ type: ActionTypes.SET_VIEW, payload: view });
  }, []);

  const setDbPath = useCallback((path) => {
    dispatch({ type: ActionTypes.SET_DB_PATH, payload: path });
  }, []);

  const setStats = useCallback((stats) => {
    dispatch({ type: ActionTypes.SET_STATS, payload: stats });
  }, []);

  const setImportFile = useCallback((file) => {
    dispatch({ type: ActionTypes.SET_IMPORT_FILE, payload: file });
  }, []);

  const setImporting = useCallback((importing) => {
    dispatch({ type: ActionTypes.SET_IMPORTING, payload: importing });
  }, []);

  const setImportProgress = useCallback((progress) => {
    dispatch({ type: ActionTypes.SET_IMPORT_PROGRESS, payload: progress });
  }, []);

  const setValidation = useCallback((validation) => {
    dispatch({ type: ActionTypes.SET_VALIDATION, payload: validation });
  }, []);

  const setValidating = useCallback((validating) => {
    dispatch({ type: ActionTypes.SET_VALIDATING, payload: validating });
  }, []);

  const setExporting = useCallback((exporting) => {
    dispatch({ type: ActionTypes.SET_EXPORTING, payload: exporting });
  }, []);

  const setExportProgress = useCallback((progress) => {
    dispatch({ type: ActionTypes.SET_EXPORT_PROGRESS, payload: progress });
  }, []);

  const setLastExport = useCallback((exportInfo) => {
    dispatch({ type: ActionTypes.SET_LAST_EXPORT, payload: exportInfo });
  }, []);

  const setHealthCheck = useCallback((result) => {
    dispatch({ type: ActionTypes.SET_HEALTH_CHECK, payload: result });
  }, []);

  const setCheckingHealth = useCallback((checking) => {
    dispatch({ type: ActionTypes.SET_CHECKING_HEALTH, payload: checking });
  }, []);

  const setLicense = useCallback((licenseData) => {
    dispatch({ type: ActionTypes.SET_LICENSE, payload: licenseData });
  }, []);

  const clearLicense = useCallback(() => {
    dispatch({ type: ActionTypes.CLEAR_LICENSE });
  }, []);

  const setSettings = useCallback((settings) => {
    dispatch({ type: ActionTypes.SET_SETTINGS, payload: settings });
  }, []);

  const updateRCASP = useCallback((updates) => {
    dispatch({ type: ActionTypes.UPDATE_RCASP, payload: updates });
  }, []);

  const updateExportOptions = useCallback((updates) => {
    dispatch({ type: ActionTypes.UPDATE_EXPORT_OPTIONS, payload: updates });
  }, []);

  const updateAdvanced = useCallback((updates) => {
    dispatch({ type: ActionTypes.UPDATE_ADVANCED, payload: updates });
  }, []);

  const toggleRightPanel = useCallback(() => {
    dispatch({ type: ActionTypes.TOGGLE_RIGHT_PANEL });
  }, []);

  const addLog = useCallback((message) => {
    dispatch({ type: ActionTypes.ADD_LOG, payload: message });
  }, []);

  const addNotification = useCallback((notification) => {
    dispatch({ type: ActionTypes.ADD_NOTIFICATION, payload: notification });
  }, []);

  const dismissNotification = useCallback((id) => {
    dispatch({ type: ActionTypes.DISMISS_NOTIFICATION, payload: id });
  }, []);

  const actions = useMemo(() => ({
      setView,
      setDbPath,
      setStats,
      setImportFile,
      setImporting,
      setImportProgress,
      setValidation,
      setValidating,
      setExporting,
      setExportProgress,
      setLastExport,
      setHealthCheck,
      setCheckingHealth,
      setLicense,
      clearLicense,
      setSettings,
      updateRCASP,
      updateExportOptions,
      updateAdvanced,
      toggleRightPanel,
      addLog,
      addNotification,
      dismissNotification,
  }), [
      setView, setDbPath, setStats, setImportFile, setImporting,
      setImportProgress, setValidation, setValidating, setExporting,
      setExportProgress, setLastExport, setHealthCheck, setCheckingHealth,
      setLicense, clearLicense, setSettings, updateRCASP, updateExportOptions,
      updateAdvanced, toggleRightPanel, addLog, addNotification, dismissNotification,
  ]);

  const isPro = useMemo(() => {
    return state.license?.status === 'active' &&
           (!state.license?.expiresAt || new Date(state.license.expiresAt) > new Date());
  }, [state.license]);

  const value = useMemo(() => ({ state, actions, isPro }), [state, actions, isPro]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

// Hook to use app context
export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}

export default AppContext;

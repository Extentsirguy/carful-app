import { useState, useEffect, useCallback } from 'react';

/**
 * Hook for managing settings with electron-store persistence.
 * Uses the carful.settings API exposed through the preload script.
 */
export function useSettings(key, defaultValue) {
  const [value, setValue] = useState(defaultValue);
  const [loading, setLoading] = useState(true);

  // Load setting on mount
  useEffect(() => {
    async function loadSetting() {
      try {
        if (window.carful?.settings?.get) {
          const stored = await window.carful.settings.get(key);
          if (stored !== undefined) {
            setValue(stored);
          }
        }
      } catch (error) {
        console.error(`Failed to load setting ${key}:`, error);
      } finally {
        setLoading(false);
      }
    }

    loadSetting();
  }, [key]);

  // Update setting
  const updateValue = useCallback(
    async (newValue) => {
      setValue(newValue);
      try {
        if (window.carful?.settings?.set) {
          await window.carful.settings.set(key, newValue);
        }
      } catch (error) {
        console.error(`Failed to save setting ${key}:`, error);
      }
    },
    [key]
  );

  return [value, updateValue, loading];
}

/**
 * Hook for loading all settings at once.
 */
export function useAllSettings() {
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadAll() {
      try {
        if (window.carful?.settings?.getAll) {
          const allSettings = await window.carful.settings.getAll();
          setSettings(allSettings || {});
        }
      } catch (error) {
        console.error('Failed to load settings:', error);
      } finally {
        setLoading(false);
      }
    }

    loadAll();
  }, []);

  const updateSetting = useCallback(async (key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    try {
      if (window.carful?.settings?.set) {
        await window.carful.settings.set(key, value);
      }
    } catch (error) {
      console.error(`Failed to save setting ${key}:`, error);
    }
  }, []);

  return { settings, updateSetting, loading };
}

export default useSettings;

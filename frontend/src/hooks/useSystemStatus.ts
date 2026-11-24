import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../services/apiClient';
import { SystemStatusState } from '../types';

export function useSystemStatus() {
  const [state, setState] = useState<SystemStatusState>({
    health: null,
    readiness: null,
    platform: null,
    isLoading: true,
    error: null,
    backendReachable: false,
    databaseReady: false,
    lastChecked: null,
  });

  const fetchStatus = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      // 1. Check Liveness Probe
      const healthData = await apiClient.getHealth();

      // 2. Check Database Readiness Probe
      const readinessData = await apiClient.getReadiness();

      // 3. Check Platform Info
      const platformData = await apiClient.getPlatformInfo();

      const isDbReady = readinessData.database.ready === true;

      setState({
        health: healthData,
        readiness: readinessData,
        platform: platformData,
        isLoading: false,
        error: isDbReady ? null : (readinessData.database.error || 'Database service degraded'),
        backendReachable: true,
        databaseReady: isDbReady,
        lastChecked: new Date(),
      });
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : 'Unable to connect to backend service';

      setState({
        health: null,
        readiness: null,
        platform: null,
        isLoading: false,
        error: errorMessage,
        backendReachable: false,
        databaseReady: false,
        lastChecked: new Date(),
      });
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  return {
    ...state,
    refresh: fetchStatus,
  };
}

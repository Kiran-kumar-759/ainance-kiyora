import React from 'react';
import { AppShell } from '../layouts/AppShell';
import { SystemStatusView } from '../features/status/SystemStatusView';
import { useSystemStatus } from '../hooks/useSystemStatus';

export const App: React.FC = () => {
  const {
    health,
    readiness,
    platform,
    isLoading,
    error,
    backendReachable,
    databaseReady,
    lastChecked,
    refresh,
  } = useSystemStatus();

  return (
    <AppShell
      backendReachable={backendReachable}
      databaseReady={databaseReady}
      isLoading={isLoading}
      onRefresh={refresh}
    >
      <SystemStatusView
        health={health}
        readiness={readiness}
        platform={platform}
        isLoading={isLoading}
        error={error}
        backendReachable={backendReachable}
        databaseReady={databaseReady}
        lastChecked={lastChecked}
        onRefresh={refresh}
      />
    </AppShell>
  );
};

export default App;

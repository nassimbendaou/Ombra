import React, { useState, useEffect } from 'react';
import { Zap, Wifi, WifiOff } from 'lucide-react';
import { getSystemStatus } from '../lib/api';

export default function StatusIndicator({ compact = false }) {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    const fetchStatus = () => {
      getSystemStatus().then(setStatus).catch(() => {});
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  if (!status) return null;

  const ollamaOnline = status.ollama?.status === 'online';
  const apiConfigured = status.cloud_api?.status === 'configured';

  if (compact) {
    return (
      <div className="flex flex-col items-center gap-2" data-testid="agent-status-indicator">
        <div className={`w-2.5 h-2.5 rounded-full ${
          ollamaOnline
            ? 'bg-[hsl(var(--status-ok))] shadow-[0_0_18px_hsl(var(--status-ok)/0.25)]'
            : apiConfigured
              ? 'bg-[hsl(var(--status-warn))] shadow-[0_0_18px_hsl(var(--status-warn)/0.25)]'
              : 'bg-[hsl(var(--status-err))] shadow-[0_0_18px_hsl(var(--status-err)/0.25)]'
        }`} />
      </div>
    );
  }

  return (
    <div className="space-y-2" data-testid="agent-status-indicator">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${
          ollamaOnline
            ? 'bg-[hsl(var(--status-ok))] shadow-[0_0_12px_hsl(var(--status-ok)/0.3)]'
            : 'bg-[hsl(var(--status-err))] shadow-[0_0_12px_hsl(var(--status-err)/0.3)]'
        }`} />
        <span className="text-xs text-muted-foreground">Ollama {ollamaOnline ? 'Online' : 'Offline'}</span>
      </div>
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${
          apiConfigured
            ? 'bg-[hsl(var(--status-ok))] shadow-[0_0_12px_hsl(var(--status-ok)/0.3)]'
            : 'bg-[hsl(var(--status-err))] shadow-[0_0_12px_hsl(var(--status-err)/0.3)]'
        }`} />
        <span className="text-xs text-muted-foreground">Cloud API {apiConfigured ? 'Ready' : 'Not Set'}</span>
      </div>
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import {
  Webhook, Loader2, Shield, Clock, CheckCircle2, XCircle,
  ToggleLeft, ToggleRight, FileText, Filter, Zap, Eye
} from 'lucide-react';
import { getHooks, getHooksLog, enableHook, disableHook } from '../lib/api';
import { toast } from 'sonner';

export default function PluginHooks() {
  const [hooks, setHooks] = useState([]);
  const [log, setLog] = useState([]);
  const [tab, setTab] = useState('hooks'); // hooks | log
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [hooksData, logData] = await Promise.all([getHooks(), getHooksLog()]);
      setHooks(hooksData.hooks || []);
      setLog(logData.entries || logData.log || []);
    } catch (e) {
      toast.error('Failed to load hooks');
    }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const handleToggle = async (hookName, currentEnabled) => {
    try {
      if (currentEnabled) {
        await disableHook(hookName);
        toast.success(`Hook "${hookName}" disabled`);
      } else {
        await enableHook(hookName);
        toast.success(`Hook "${hookName}" enabled`);
      }
      fetchData();
    } catch (e) {
      toast.error('Failed to toggle hook');
    }
  };

  const enabledCount = hooks.filter(h => h.enabled).length;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center">
              <Webhook className="w-5 h-5 text-amber-400" />
            </div>
            Plugin Hooks
          </h1>
          <p className="text-muted-foreground mt-1">
            Configure pre/post tool hooks and review execution logs
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
          <Loader2 className={`w-3 h-3 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Total Hooks', value: hooks.length, icon: Webhook, color: 'amber' },
          { label: 'Active', value: enabledCount, icon: Zap, color: 'emerald' },
          { label: 'Log Entries', value: log.length, icon: FileText, color: 'blue' },
        ].map((s, i) => (
          <motion.div key={s.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
            <Card className="bg-card/50 border-border/40">
              <CardContent className="p-4 flex items-center gap-3">
                <div className={`w-9 h-9 rounded-lg bg-${s.color}-500/20 flex items-center justify-center`}>
                  <s.icon className={`w-4 h-4 text-${s.color}-400`} />
                </div>
                <div>
                  <p className="text-2xl font-bold">{s.value}</p>
                  <p className="text-xs text-muted-foreground">{s.label}</p>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-secondary/30 rounded-lg w-fit">
        <Button
          variant={tab === 'hooks' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setTab('hooks')}
          className={tab !== 'hooks' ? 'text-muted-foreground' : ''}
        >
          <Shield className="w-4 h-4 mr-1.5" />
          Hooks ({hooks.length})
        </Button>
        <Button
          variant={tab === 'log' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setTab('log')}
          className={tab !== 'log' ? 'text-muted-foreground' : ''}
        >
          <FileText className="w-4 h-4 mr-1.5" />
          Execution Log
        </Button>
      </div>

      {/* Hooks Tab */}
      {tab === 'hooks' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-2">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : hooks.length === 0 ? (
            <Card className="bg-card/50 border-border/40">
              <CardContent className="p-8 text-center">
                <Shield className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
                <p className="text-muted-foreground">No hooks registered</p>
              </CardContent>
            </Card>
          ) : (
            hooks.map((hook, i) => (
              <motion.div
                key={hook.name || i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
              >
                <Card className="bg-card/50 border-border/40 hover:border-amber-500/20 transition-colors">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className={`w-2 h-2 rounded-full ${hook.enabled ? 'bg-emerald-400' : 'bg-neutral-600'}`} />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <h3 className="font-semibold text-sm">{hook.name}</h3>
                            <Badge variant="outline" className="text-[10px] h-4">
                              {hook.type || 'pre'}
                            </Badge>
                            {hook.tool && (
                              <Badge className="bg-amber-500/15 text-amber-400 border-0 text-[10px] h-4">
                                {hook.tool}
                              </Badge>
                            )}
                          </div>
                          {hook.description && (
                            <p className="text-xs text-muted-foreground mt-0.5">{hook.description}</p>
                          )}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleToggle(hook.name, hook.enabled)}
                        className={hook.enabled ? 'text-emerald-400' : 'text-muted-foreground'}
                      >
                        {hook.enabled ?
                          <ToggleRight className="w-5 h-5" /> :
                          <ToggleLeft className="w-5 h-5" />
                        }
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))
          )}
        </motion.div>
      )}

      {/* Log Tab */}
      {tab === 'log' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <Card className="bg-card/50 border-border/40">
            {log.length === 0 ? (
              <CardContent className="p-8 text-center">
                <Clock className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
                <p className="text-muted-foreground">No execution logs yet</p>
              </CardContent>
            ) : (
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border/40 text-muted-foreground text-xs">
                        <th className="text-left p-3 font-medium">Time</th>
                        <th className="text-left p-3 font-medium">Hook</th>
                        <th className="text-left p-3 font-medium">Tool</th>
                        <th className="text-left p-3 font-medium">Action</th>
                        <th className="text-left p-3 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {log.map((entry, i) => (
                        <tr key={i} className="border-b border-border/20 hover:bg-secondary/20">
                          <td className="p-3 font-mono text-xs text-muted-foreground">
                            {entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : '—'}
                          </td>
                          <td className="p-3 font-medium text-xs">{entry.hook || '—'}</td>
                          <td className="p-3 font-mono text-xs text-amber-400">{entry.tool || '—'}</td>
                          <td className="p-3 text-xs">{entry.action || '—'}</td>
                          <td className="p-3">
                            {entry.status === 'success' || entry.allowed ? (
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                            ) : entry.status === 'blocked' ? (
                              <XCircle className="w-3.5 h-3.5 text-red-400" />
                            ) : (
                              <span className="text-xs text-muted-foreground">{entry.status || '—'}</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            )}
          </Card>
        </motion.div>
      )}
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../components/ui/card';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '../components/ui/alert-dialog';
import { Terminal, FolderOpen, Send, Shield, AlertTriangle, CheckCircle2, Info } from 'lucide-react';
import { getPermissions, updatePermissions } from '../lib/api';
import { toast } from 'sonner';

const permissionItems = [
  {
    key: 'terminal',
    label: 'Terminal Access',
    description: 'Allow Ombra to execute shell commands on your system. Commands are sandboxed with safety checks.',
    icon: Terminal,
    dangerous: true,
    rationale: 'Needed for running code, checking system status, installing packages, and automating tasks.',
  },
  {
    key: 'filesystem',
    label: 'File System Access',
    description: 'Allow Ombra to read and write files. Operations are logged and restricted to safe directories.',
    icon: FolderOpen,
    dangerous: true,
    rationale: 'Needed for reading project files, saving outputs, and managing configuration.',
  },
  {
    key: 'telegram',
    label: 'Telegram Integration',
    description: 'Allow Ombra to send messages and daily summaries via Telegram bot. Requires bot token setup in Settings.',
    icon: Send,
    dangerous: false,
    rationale: 'Enables remote notifications, daily summaries, and quick interactions via Telegram.',
  },
];

export default function Permissions() {
  const [perms, setPerms] = useState({ terminal: false, filesystem: false, telegram: false });
  const [loading, setLoading] = useState(true);
  const [pendingChange, setPendingChange] = useState(null);

  useEffect(() => {
    getPermissions().then(p => {
      setPerms(p);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const handleToggle = async (key, value) => {
    const item = permissionItems.find(p => p.key === key);
    if (item?.dangerous && value) {
      setPendingChange({ key, value });
      return;
    }
    await applyChange(key, value);
  };

  const applyChange = async (key, value) => {
    try {
      const result = await updatePermissions({ [key]: value });
      setPerms(result);
      toast.success(`${key} access ${value ? 'granted' : 'revoked'}`);
    } catch (e) {
      toast.error('Failed to update permission');
    }
    setPendingChange(null);
  };

  if (loading) {
    return <div className="space-y-4"><div className="h-8 w-48 bg-secondary/60 rounded animate-pulse" /><div className="h-48 bg-card/40 rounded-xl animate-pulse" /></div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Permissions</h1>
        <p className="text-sm text-muted-foreground mt-1">Control what Ombra can access. All actions are logged for transparency.</p>
      </div>

      <div className="grid gap-4">
        {permissionItems.map((item) => (
          <motion.div
            key={item.key}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.15 }}
          >
            <Card className="bg-card/80 backdrop-blur border-border/60 transition-colors duration-200 hover:border-border/80">
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
                      perms[item.key]
                        ? 'bg-[hsl(var(--status-ok)/0.15)] text-[hsl(var(--status-ok))]'
                        : 'bg-secondary/60 text-muted-foreground'
                    }`}>
                      <item.icon className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-semibold">{item.label}</h3>
                        {item.dangerous && (
                          <Badge variant="outline" className="text-[10px] text-[hsl(var(--status-warn))] border-[hsl(var(--status-warn)/0.3)]">
                            <AlertTriangle className="w-3 h-3 mr-1" />Elevated
                          </Badge>
                        )}
                        {perms[item.key] && (
                          <Badge variant="outline" className="text-[10px] text-[hsl(var(--status-ok))] border-[hsl(var(--status-ok)/0.3)]">
                            <CheckCircle2 className="w-3 h-3 mr-1" />Active
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">{item.description}</p>
                      <div className="flex items-start gap-1.5 mt-2 p-2 rounded-md bg-secondary/30">
                        <Info className="w-3 h-3 mt-0.5 text-muted-foreground flex-shrink-0" />
                        <p className="text-[11px] text-muted-foreground">{item.rationale}</p>
                      </div>
                    </div>
                  </div>
                  <Switch
                    checked={perms[item.key]}
                    onCheckedChange={(v) => handleToggle(item.key, v)}
                    data-testid={`permissions-${item.key}-switch`}
                  />
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Confirmation Dialog for dangerous permissions */}
      <AlertDialog open={!!pendingChange} onOpenChange={(open) => !open && setPendingChange(null)}>
        <AlertDialogContent data-testid="permissions-confirm-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-[hsl(var(--status-warn))]" />
              Grant {pendingChange?.key} Access?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This gives Ombra the ability to {pendingChange?.key === 'terminal' ? 'execute commands on your system' : 'read and write files'}.
              All operations are logged and safety-checked, but please grant only if you trust the current context.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => pendingChange && applyChange(pendingChange.key, pendingChange.value)}>
              Grant Access
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

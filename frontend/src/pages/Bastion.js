import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Separator } from '../components/ui/separator';
import {
  Monitor, Wifi, WifiOff, Loader2, Shield, Key, User, RefreshCw,
  Copy, CheckCircle2, XCircle, AlertCircle, Server, Terminal, Download,
  Maximize2, Minimize2, ExternalLink
} from 'lucide-react';
import { getBastionStatus, setupBastion, restartBastion, getClaudeStatus, setClaudeKey } from '../lib/api';
import { toast } from 'sonner';

export default function Bastion() {
  const [status, setStatus] = useState(null);
  const [claude, setClaude] = useState(null);
  const [loading, setLoading] = useState(true);
  const [setupLoading, setSetupLoading] = useState(false);
  const [claudeLoading, setClaudeLoading] = useState(false);
  const [form, setForm] = useState({ username: 'ombra-rdp', password: '' });
  const [claudeKey, setClaudeKeyInput] = useState('');
  const [copied, setCopied] = useState(false);
  const [vncExpanded, setVncExpanded] = useState(false);
  const [vncConnected, setVncConnected] = useState(false);
  const iframeRef = useRef(null);

  const NOVNC_URL = status?.server_ip
    ? `/novnc/vnc.html?autoconnect=true&resize=remote&reconnect=true&reconnect_delay=3000&path=novnc/websockify`
    : null;

  const fetchData = async () => {
    setLoading(true);
    try {
      const [bastionData, claudeData] = await Promise.all([
        getBastionStatus().catch(() => null),
        getClaudeStatus().catch(() => null),
      ]);
      setStatus(bastionData);
      setClaude(claudeData);
    } catch (e) {}
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const handleSetup = async () => {
    if (!form.password || form.password.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }
    setSetupLoading(true);
    try {
      const result = await setupBastion(form.username, form.password);
      toast.success('Bastion setup complete!');
      setForm({ ...form, password: '' });
      fetchData();
    } catch (e) {
      toast.error(e.message || 'Setup failed');
    }
    setSetupLoading(false);
  };

  const handleRestart = async () => {
    try {
      await restartBastion();
      toast.success('xRDP restarted');
      fetchData();
    } catch (e) {
      toast.error(e.message || 'Restart failed');
    }
  };

  const handleClaudeKey = async () => {
    if (!claudeKey.trim()) { toast.error('Enter an API key'); return; }
    setClaudeLoading(true);
    try {
      await setClaudeKey(claudeKey.trim());
      toast.success('Claude API key configured and validated!');
      setClaudeKeyInput('');
      fetchData();
    } catch (e) {
      toast.error(e.message || 'Invalid API key');
    }
    setClaudeLoading(false);
  };

  const copyConnection = () => {
    if (status?.connection_string) {
      navigator.clipboard.writeText(status.connection_string);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast.success('Copied to clipboard');
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center">
              <Shield className="w-5 h-5 text-indigo-400" />
            </div>
            Bastion & Providers
          </h1>
          <p className="text-muted-foreground mt-1">
            Remote desktop access and AI provider configuration
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
          <RefreshCw className={`w-3 h-3 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* ── Claude API Key Section ──────────────────────────────────────── */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <Card className="bg-card/50 border-border/40">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-orange-500/20 flex items-center justify-center">
                <span className="text-orange-400 text-sm font-bold">C</span>
              </div>
              Claude Sonnet
              {claude?.configured ? (
                <Badge className="bg-emerald-500/20 text-emerald-400 border-0 text-[10px]">Configured</Badge>
              ) : (
                <Badge variant="outline" className="text-[10px]">Not configured</Badge>
              )}
            </CardTitle>
            <CardDescription>
              Add your Anthropic API key to unlock Claude Sonnet for difficult tasks
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {claude?.configured ? (
              <div className="flex items-center gap-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <div className="text-sm">
                  <span className="text-emerald-300 font-medium">Active</span>
                  <span className="text-muted-foreground ml-2">
                    via {claude.source} · Model: {claude.model}
                  </span>
                </div>
              </div>
            ) : null}
            <div className="flex gap-2">
              <Input
                type="password"
                placeholder="sk-ant-api03-..."
                value={claudeKey}
                onChange={e => setClaudeKeyInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleClaudeKey()}
                className="flex-1 font-mono text-sm"
              />
              <Button onClick={handleClaudeKey} disabled={claudeLoading}>
                {claudeLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Key className="w-4 h-4 mr-1.5" />}
                {claude?.configured ? 'Update Key' : 'Set Key'}
              </Button>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Use <code className="bg-background/60 px-1 py-0.5 rounded">/claude</code> in Telegram
              or select "Claude Sonnet" in the chat to use it for complex reasoning tasks.
            </p>
          </CardContent>
        </Card>
      </motion.div>

      <Separator />

      {/* ── Bastion / RDP Section ───────────────────────────────────────── */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
        <Card className="bg-card/50 border-border/40">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center">
                <Monitor className="w-4 h-4 text-indigo-400" />
              </div>
              Remote Desktop (xRDP)
              {status?.xrdp_running ? (
                <Badge className="bg-emerald-500/20 text-emerald-400 border-0 text-[10px]">Running</Badge>
              ) : (
                <Badge variant="destructive" className="text-[10px]">Offline</Badge>
              )}
            </CardTitle>
            <CardDescription>
              Connect to the server via RDP for a full graphical desktop experience
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4">
            {loading ? (
              <div className="flex items-center gap-3 py-4">
                <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                <span className="text-muted-foreground text-sm">Checking status...</span>
              </div>
            ) : (
              <>
                {/* Connection Info */}
                {status?.xrdp_running && status?.connection_string && (
                  <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-lg p-4 space-y-3">
                    <div className="flex items-center gap-2">
                      <Wifi className="w-4 h-4 text-indigo-400" />
                      <span className="font-semibold text-sm text-indigo-300">Connection Ready</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                      <div>
                        <span className="text-muted-foreground text-xs block mb-1">Address</span>
                        <div className="flex items-center gap-2">
                          <code className="bg-background/60 px-2 py-1 rounded font-mono">
                            {status.connection_string}
                          </code>
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={copyConnection}>
                            {copied ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> :
                              <Copy className="w-3.5 h-3.5" />}
                          </Button>
                        </div>
                      </div>
                      <div>
                        <span className="text-muted-foreground text-xs block mb-1">Username</span>
                        <code className="bg-background/60 px-2 py-1 rounded font-mono">
                          {status.bastion_user || '—'}
                        </code>
                      </div>
                    </div>
                    <Separator />
                    <div className="text-xs text-muted-foreground space-y-1">
                      <p><strong>Windows:</strong> Open "Remote Desktop Connection" → enter the address above</p>
                      <p><strong>macOS:</strong> Use "Microsoft Remote Desktop" from the App Store</p>
                      <p><strong>Linux:</strong> <code className="bg-background/60 px-1 py-0.5 rounded">xfreerdp /v:{status.connection_string} /u:{status.bastion_user}</code></p>
                    </div>
                  </div>
                )}

                {/* Status Cards */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-background/30 rounded-lg p-3 text-center">
                    <Server className="w-5 h-5 mx-auto mb-1 text-muted-foreground" />
                    <p className="text-xs text-muted-foreground">Server IP</p>
                    <p className="text-sm font-mono font-medium">{status?.server_ip || '—'}</p>
                  </div>
                  <div className="bg-background/30 rounded-lg p-3 text-center">
                    <Terminal className="w-5 h-5 mx-auto mb-1 text-muted-foreground" />
                    <p className="text-xs text-muted-foreground">RDP Port</p>
                    <p className="text-sm font-mono font-medium">{status?.rdp_port || '3389'}</p>
                  </div>
                  <div className="bg-background/30 rounded-lg p-3 text-center">
                    <User className="w-5 h-5 mx-auto mb-1 text-muted-foreground" />
                    <p className="text-xs text-muted-foreground">User</p>
                    <p className="text-sm font-mono font-medium">
                      {status?.user_exists ? status.bastion_user : 'Not created'}
                    </p>
                  </div>
                </div>

                {/* Setup Form */}
                {!status?.xrdp_running || !status?.user_exists ? (
                  <div className="border border-border/40 rounded-lg p-4 space-y-3">
                    <div className="flex items-center gap-2 mb-2">
                      <AlertCircle className="w-4 h-4 text-amber-400" />
                      <span className="text-sm font-medium text-amber-300">Setup Required</span>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs text-muted-foreground mb-1 block">Username</label>
                        <Input
                          value={form.username}
                          onChange={e => setForm({ ...form, username: e.target.value })}
                          placeholder="ombra-rdp"
                          className="font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-muted-foreground mb-1 block">Password</label>
                        <Input
                          type="password"
                          value={form.password}
                          onChange={e => setForm({ ...form, password: e.target.value })}
                          placeholder="min 8 characters"
                        />
                      </div>
                    </div>
                    <Button onClick={handleSetup} disabled={setupLoading} className="w-full">
                      {setupLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> :
                        <Shield className="w-4 h-4 mr-2" />}
                      {setupLoading ? 'Setting up xRDP + Desktop...' : 'Setup Bastion Access'}
                    </Button>
                    <p className="text-[10px] text-muted-foreground text-center">
                      This will install xRDP + XFCE desktop, create the user, and open port 3389
                    </p>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={handleRestart}>
                      <RefreshCw className="w-3 h-3 mr-1.5" />
                      Restart xRDP
                    </Button>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </motion.div>

      <Separator />

      {/* ── Live Desktop (noVNC) Section ────────────────────────────────── */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
        <Card className="bg-card/50 border-border/40">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-violet-500/20 flex items-center justify-center">
                    <Monitor className="w-4 h-4 text-violet-400" />
                  </div>
                  Live Desktop
                  {vncConnected ? (
                    <Badge className="bg-emerald-500/20 text-emerald-400 border-0 text-[10px]">Connected</Badge>
                  ) : (
                    <Badge variant="outline" className="text-[10px]">Standby</Badge>
                  )}
                </CardTitle>
                <CardDescription className="mt-1">
                  Interact with the server desktop directly in your browser via noVNC
                </CardDescription>
              </div>
              <div className="flex gap-2">
                {NOVNC_URL && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => window.open(NOVNC_URL, '_blank')}
                  >
                    <ExternalLink className="w-3 h-3 mr-1.5" />
                    Pop Out
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setVncExpanded(!vncExpanded)}
                >
                  {vncExpanded ? (
                    <><Minimize2 className="w-3 h-3 mr-1.5" />Collapse</>
                  ) : (
                    <><Maximize2 className="w-3 h-3 mr-1.5" />Expand</>
                  )}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {!status?.xrdp_running ? (
              <div className="flex items-center gap-3 py-8 justify-center">
                <WifiOff className="w-5 h-5 text-muted-foreground" />
                <span className="text-muted-foreground text-sm">
                  Start xRDP above to enable the live desktop viewer
                </span>
              </div>
            ) : NOVNC_URL ? (
              <div className="space-y-3">
                <div
                  className={`relative rounded-lg overflow-hidden border border-border/40 bg-black transition-all duration-300 ${
                    vncExpanded ? 'h-[80vh]' : 'h-[500px]'
                  }`}
                >
                  <iframe
                    ref={iframeRef}
                    src={NOVNC_URL}
                    title="noVNC Remote Desktop"
                    className="w-full h-full border-0"
                    onLoad={() => setVncConnected(true)}
                    onError={() => setVncConnected(false)}
                    allow="clipboard-read; clipboard-write"
                  />
                </div>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>
                    noVNC → localhost:5901 (proxied via nginx)
                  </span>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-[10px]"
                      onClick={() => {
                        if (iframeRef.current) {
                          iframeRef.current.src = NOVNC_URL;
                          setVncConnected(false);
                        }
                      }}
                    >
                      <RefreshCw className="w-3 h-3 mr-1" />
                      Reconnect
                    </Button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-3 py-8 justify-center">
                <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                <span className="text-muted-foreground text-sm">Loading connection info...</span>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}

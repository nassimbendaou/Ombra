import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Separator } from '../components/ui/separator';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import {
  Plug, Plus, Trash2, RefreshCw, Server, Wifi, WifiOff,
  Terminal, Globe, Loader2, Wrench, Unplug, Zap, AlertCircle
} from 'lucide-react';
import { getMcpStatus, connectMcpServer, disconnectMcpServer } from '../lib/api';
import { toast } from 'sonner';

export default function McpManager() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showConnect, setShowConnect] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [form, setForm] = useState({
    server_id: '', transport: 'stdio', command: '', args: '', url: ''
  });

  const PRESETS = [
    { id: 'filesystem', label: 'Filesystem', command: 'npx', args: '-y @modelcontextprotocol/server-filesystem /tmp/ombra_workspace' },
    { id: 'fetch', label: 'Web Fetch', command: 'npx', args: '-y @modelcontextprotocol/server-fetch' },
    { id: 'memory', label: 'Memory', command: 'npx', args: '-y @modelcontextprotocol/server-memory' },
    { id: 'github', label: 'GitHub', command: 'npx', args: '-y @modelcontextprotocol/server-github' },
    { id: 'puppeteer', label: 'Puppeteer', command: 'npx', args: '-y @modelcontextprotocol/server-puppeteer' },
  ];

  const applyPreset = (preset) => {
    setForm({ ...form, server_id: preset.id, command: preset.command, args: preset.args, transport: 'stdio' });
  };

  const fetchStatus = () => {
    setLoading(true);
    getMcpStatus()
      .then(data => { setStatus(data.status || data); setLoading(false); })
      .catch(() => setLoading(false));
  };

  useEffect(() => { fetchStatus(); }, []);

  const handleConnect = async () => {
    if (!form.server_id.trim()) return toast.error('Server ID is required');
    setConnecting(true);
    try {
      const args = form.args ? form.args.split(' ').filter(Boolean) : [];
      await connectMcpServer(
        form.server_id,
        form.transport === 'stdio' ? form.command : '',
        form.transport === 'stdio' ? args : [],
        form.transport === 'sse' ? form.url : ''
      );
      toast.success(`Connected to ${form.server_id}`);
      setShowConnect(false);
      setForm({ server_id: '', transport: 'stdio', command: '', args: '', url: '' });
      fetchStatus();
    } catch (e) {
      toast.error(e.message || 'Connection failed');
    }
    setConnecting(false);
  };

  const handleDisconnect = async (serverId) => {
    try {
      await disconnectMcpServer(serverId);
      toast.success(`Disconnected from ${serverId}`);
      fetchStatus();
    } catch (e) {
      toast.error(e.message || 'Disconnect failed');
    }
  };

  const servers = status?.servers || [];
  const totalTools = status?.total_tools || 0;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-500/20 flex items-center justify-center">
              <Plug className="w-5 h-5 text-violet-400" />
            </div>
            MCP Servers
          </h1>
          <p className="text-muted-foreground mt-1">
            Connect external tool servers via Model Context Protocol
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchStatus} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button size="sm" onClick={() => setShowConnect(true)} className="bg-violet-600 hover:bg-violet-700">
            <Plus className="w-4 h-4 mr-2" />
            Connect Server
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="bg-card/50 border-border/40">
          <CardContent className="p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/15 flex items-center justify-center">
              <Server className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-2xl font-bold">{status?.connected || 0}</p>
              <p className="text-xs text-muted-foreground">Connected</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card/50 border-border/40">
          <CardContent className="p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/15 flex items-center justify-center">
              <Wrench className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <p className="text-2xl font-bold">{totalTools}</p>
              <p className="text-xs text-muted-foreground">Tools Available</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card/50 border-border/40">
          <CardContent className="p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-amber-500/15 flex items-center justify-center">
              <Zap className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-2xl font-bold">{status?.total_servers || 0}</p>
              <p className="text-xs text-muted-foreground">Total Servers</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Server List */}
      {loading ? (
        <Card className="bg-card/50 border-border/40">
          <CardContent className="p-12 flex items-center justify-center">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </CardContent>
        </Card>
      ) : servers.length === 0 ? (
        <Card className="bg-card/50 border-border/40">
          <CardContent className="p-12 text-center">
            <Unplug className="w-12 h-12 text-muted-foreground/40 mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-1">No MCP Servers Connected</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Connect an MCP server to extend Ombra with external tools
            </p>
            <Button onClick={() => setShowConnect(true)} className="bg-violet-600 hover:bg-violet-700">
              <Plus className="w-4 h-4 mr-2" />
              Connect Your First Server
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {servers.map((server, i) => (
            <motion.div
              key={server.server_id || server.id || i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <Card className="bg-card/50 border-border/40 hover:border-border/70 transition-colors">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                        server.connected ? 'bg-emerald-500/15' : 'bg-red-500/15'
                      }`}>
                        {server.transport === 'sse' ?
                          <Globe className={`w-5 h-5 ${server.connected ? 'text-emerald-400' : 'text-red-400'}`} /> :
                          <Terminal className={`w-5 h-5 ${server.connected ? 'text-emerald-400' : 'text-red-400'}`} />
                        }
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold">{server.server_id || server.id}</span>
                          <Badge variant={server.connected ? 'default' : 'destructive'} className="text-[10px] h-5">
                            {server.connected ? 'Connected' : 'Disconnected'}
                          </Badge>
                          <Badge variant="outline" className="text-[10px] h-5">
                            {server.transport || 'stdio'}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {server.tools || 0} tools available
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDisconnect(server.server_id || server.id)}
                      className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                  {server.tool_names && server.tool_names.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-border/30 flex flex-wrap gap-1.5">
                      {server.tool_names.map((tool, j) => (
                        <Badge key={j} variant="secondary" className="text-[10px] font-mono">
                          {tool}
                        </Badge>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      )}

      {/* Connect Dialog */}
      <Dialog open={showConnect} onOpenChange={setShowConnect}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plug className="w-5 h-5 text-violet-400" />
              Connect MCP Server
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {/* Quick Presets */}
            <div>
              <label className="text-sm font-medium mb-1.5 block">Quick Start</label>
              <div className="flex flex-wrap gap-1.5">
                {PRESETS.map(p => (
                  <Button key={p.id} variant="outline" size="sm" className="text-xs h-7"
                    onClick={() => applyPreset(p)}>
                    <Zap className="w-3 h-3 mr-1" />{p.label}
                  </Button>
                ))}
              </div>
            </div>
            <Separator />
            <div>
              <label className="text-sm font-medium mb-1.5 block">Server ID</label>
              <Input
                placeholder="my-server"
                value={form.server_id}
                onChange={e => setForm({ ...form, server_id: e.target.value })}
              />
            </div>
            <div>
              <label className="text-sm font-medium mb-1.5 block">Transport</label>
              <div className="flex gap-2">
                <Button
                  variant={form.transport === 'stdio' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setForm({ ...form, transport: 'stdio' })}
                >
                  <Terminal className="w-4 h-4 mr-1.5" /> Stdio
                </Button>
                <Button
                  variant={form.transport === 'sse' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setForm({ ...form, transport: 'sse' })}
                >
                  <Globe className="w-4 h-4 mr-1.5" /> SSE
                </Button>
              </div>
            </div>
            {form.transport === 'stdio' ? (
              <>
                <div>
                  <label className="text-sm font-medium mb-1.5 block">Command</label>
                  <Input
                    placeholder="npx"
                    value={form.command}
                    onChange={e => setForm({ ...form, command: e.target.value })}
                  />
                  <p className="text-[11px] text-muted-foreground mt-1">The executable to run (e.g. <code>npx</code>, <code>node</code>, <code>python</code>)</p>
                </div>
                <div>
                  <label className="text-sm font-medium mb-1.5 block">Arguments</label>
                  <Input
                    placeholder="-y @modelcontextprotocol/server-filesystem /path"
                    value={form.args}
                    onChange={e => setForm({ ...form, args: e.target.value })}
                  />
                  <p className="text-[11px] text-muted-foreground mt-1">Space-separated arguments passed to the command</p>
                </div>
              </>
            ) : (
              <div>
                <label className="text-sm font-medium mb-1.5 block">Server URL</label>
                <Input
                  placeholder="http://localhost:3001/sse"
                  value={form.url}
                  onChange={e => setForm({ ...form, url: e.target.value })}
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConnect(false)}>Cancel</Button>
            <Button onClick={handleConnect} disabled={connecting} className="bg-violet-600 hover:bg-violet-700">
              {connecting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Plug className="w-4 h-4 mr-2" />}
              Connect
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

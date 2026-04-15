import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Separator } from '../components/ui/separator';
import {
  Github, Link, Unlink, Loader2, GitPullRequest, AlertCircle,
  CheckCircle2, XCircle, ExternalLink, GitBranch, Tag, Clock
} from 'lucide-react';
import { getGithubStatus, getGithubConfig, setGithubConfig } from '../lib/api';
import { toast } from 'sonner';

export default function GithubIntegration() {
  const [status, setStatus] = useState(null);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ owner: '', repo: '', token: '' });

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [statusData, configData] = await Promise.all([
        getGithubStatus().catch(e => ({ connected: false, error: e.message })),
        getGithubConfig().catch(() => null),
      ]);
      setStatus(statusData);
      if (configData) {
        setConfig(configData);
        setForm(f => ({
          owner: f.owner || configData.owner || '',
          repo: f.repo || configData.repo || '',
          token: '',
        }));
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const handleSave = async () => {
    if (!form.owner.trim() || !form.repo.trim()) {
      toast.error('Owner and repository name are required');
      return;
    }
    setSaving(true);
    try {
      await setGithubConfig(form.owner.trim(), form.repo.trim(), form.token.trim());
      toast.success('GitHub configuration saved');
      setForm(f => ({ ...f, token: '' }));
      fetchAll();
    } catch (e) {
      toast.error(e.message || 'Save failed');
    }
    setSaving(false);
  };

  const connected = status?.connected;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-neutral-500/20 flex items-center justify-center">
            <Github className="w-5 h-5 text-neutral-300" />
          </div>
          GitHub Integration
        </h1>
        <p className="text-muted-foreground mt-1">
          Manage repositories, pull requests, and issues
        </p>
      </div>

      {/* Connection Status */}
      <Card className="bg-card/50 border-border/40">
        <CardContent className="p-5">
          {loading ? (
            <div className="flex items-center gap-3">
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
              <span className="text-muted-foreground">Checking connection...</span>
            </div>
          ) : connected ? (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                <span className="font-semibold">Connected to GitHub</span>
                <Badge className="bg-emerald-500/20 text-emerald-400 border-0">Active</Badge>
              </div>
              {(config?.owner || status.repo) && (
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  {config?.owner && <span>Owner: <span className="text-foreground font-medium font-mono">{config.owner}</span></span>}
                  {config?.repo && <><Separator orientation="vertical" className="h-4" /><span className="font-mono">{config.repo}</span></>}
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <XCircle className="w-5 h-5 text-red-400" />
              <span className="font-semibold">Not Connected</span>
              {status?.error && <span className="text-xs text-muted-foreground">{status.error}</span>}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Configuration Form */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <Card className="bg-card/50 border-border/40">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Github className="w-4 h-4" />
              Repository Configuration
              {config?.token_set && (
                <Badge className="bg-emerald-500/20 text-emerald-400 border-0 text-[10px]">Token set</Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted-foreground mb-1.5 block">GitHub Owner / Org</label>
                <Input
                  placeholder="e.g. nassim-bendaou"
                  value={form.owner}
                  onChange={e => setForm(f => ({ ...f, owner: e.target.value }))}
                  className="font-mono"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1.5 block">Repository Name</label>
                <Input
                  placeholder="e.g. Ombra"
                  value={form.repo}
                  onChange={e => setForm(f => ({ ...f, repo: e.target.value }))}
                  className="font-mono"
                />
              </div>
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1.5 block">
                GitHub Token
                {config?.token_set && <span className="ml-2 text-emerald-400">({config.token_preview} — leave blank to keep current)</span>}
              </label>
              <Input
                type="password"
                placeholder={config?.token_set ? 'Leave blank to keep current token' : 'ghp_...'}
                value={form.token}
                onChange={e => setForm(f => ({ ...f, token: e.target.value }))}
                className="font-mono"
              />
            </div>
            <Button onClick={handleSave} disabled={saving} className="w-full">
              {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Github className="w-4 h-4 mr-2" />}
              Save Configuration
            </Button>
          </CardContent>
        </Card>
      </motion.div>

      {/* Feature Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          {
            icon: GitPullRequest,
            title: 'Pull Requests',
            desc: 'Create, review, and merge PRs directly from chat',
            available: connected
          },
          {
            icon: AlertCircle,
            title: 'Issues',
            desc: 'Browse, create, and manage repository issues',
            available: connected
          },
          {
            icon: GitBranch,
            title: 'Branches',
            desc: 'Create and switch between code branches',
            available: connected
          },
        ].map((item, i) => (
          <motion.div
            key={item.title}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + i * 0.05 }}
          >
            <Card className={`bg-card/50 border-border/40 ${!item.available ? 'opacity-50' : 'hover:border-neutral-400/30'} transition-colors`}>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-2">
                  <item.icon className="w-4 h-4 text-neutral-300" />
                  <h3 className="font-semibold text-sm">{item.title}</h3>
                </div>
                <p className="text-xs text-muted-foreground">{item.desc}</p>
                {!item.available && (
                  <Badge variant="outline" className="mt-3 text-[10px]">Requires connection</Badge>
                )}
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Quick Actions */}
      {connected && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
          <Card className="bg-card/50 border-border/40">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <p className="text-sm text-muted-foreground">
                Use these GitHub features via chat commands:
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-3">
                {[
                  '"Create a PR for my current changes"',
                  '"List open issues labeled bug"',
                  '"Create a branch called feature/auth"',
                  '"Review the latest pull request"',
                ].map((cmd, i) => (
                  <div key={i} className="flex items-center gap-2 bg-background/40 rounded-lg px-3 py-2">
                    <code className="text-xs text-neutral-300 flex-1">{cmd}</code>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={fetchAll}>
          <Loader2 className={`w-3 h-3 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh Status
        </Button>
      </div>
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import {
  Settings as SettingsIcon, Cpu, Cloud, Brain, Shield,
  Save, RefreshCcw, Loader2, CheckCircle2, AlertCircle, Send, Mail,
  Link2, Unlink, KeyRound
} from 'lucide-react';
import {
  getSettings, updateSettings, getHealth, testTelegram, sendTelegramMessage,
  getLearningMetrics, testEmail, getEmailProviderStatus,
  connectEmailProvider, disconnectEmailProvider
} from '../lib/api';
import { toast } from 'sonner';

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({});
  const [emailProvider, setEmailProvider] = useState(null);
  const [providerForm, setProviderForm] = useState({ email: '', app_password: '' });

  const loadEmailProvider = () => {
    getEmailProviderStatus().then(setEmailProvider).catch(() => null);
  };

  useEffect(() => {
    Promise.all([
      getSettings().catch(() => null),
      getHealth().catch(() => null),
      getEmailProviderStatus().catch(() => null),
    ]).then(([s, h, ep]) => {
      setSettings(s);
      setHealth(h);
      if (s) setForm(s);
      if (ep) setEmailProvider(ep);
      setLoading(false);
    });
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const result = await updateSettings({
        ollama_url: form.ollama_url,
        ollama_model: form.ollama_model,
        preferred_provider: form.preferred_provider,
        preferred_model: form.preferred_model,
        learning_enabled: form.learning_enabled,
        white_card_enabled: form.white_card_enabled,
        quiet_hours_start: form.quiet_hours_start,
        quiet_hours_end: form.quiet_hours_end,
        telegram_chat_id: form.telegram_chat_id,
        telegram_enabled: form.telegram_enabled,
        email_host: form.email_host,
        email_port: form.email_port ? parseInt(form.email_port) : undefined,
        email_user: form.email_user,
        email_pass: form.email_pass,
        email_from: form.email_from,
        email_enabled: form.email_enabled,
      });
      setSettings(result);
      toast.success('Settings saved');
    } catch (e) {
      toast.error('Failed to save settings');
    }
    setSaving(false);
  };

  const handleRefreshHealth = async () => {
    const h = await getHealth().catch(() => null);
    setHealth(h);
  };

  if (loading) {
    return <div className="space-y-4"><div className="h-8 w-48 bg-secondary/60 rounded animate-pulse" /></div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">Configure Ombra's behavior, models, and learning</p>
      </div>

      <Tabs defaultValue="runtime" data-testid="settings-tabs">
        <TabsList className="bg-secondary/40">
          <TabsTrigger value="runtime"><Cpu className="w-4 h-4 mr-1" />Runtime</TabsTrigger>
          <TabsTrigger value="models"><Cloud className="w-4 h-4 mr-1" />Models</TabsTrigger>
          <TabsTrigger value="learning"><Brain className="w-4 h-4 mr-1" />Learning</TabsTrigger>
          <TabsTrigger value="telegram"><Send className="w-4 h-4 mr-1" />Telegram</TabsTrigger>
          <TabsTrigger value="email"><Mail className="w-4 h-4 mr-1" />Email</TabsTrigger>
        </TabsList>

        <TabsContent value="runtime" className="mt-4 space-y-4">
          {/* Ollama Config */}
          <Card className="bg-card/80 backdrop-blur border-border/60">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Cpu className="w-5 h-5 text-primary" />
                Ollama Configuration
              </CardTitle>
              <CardDescription>Configure local model inference</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Ollama Server URL</label>
                <Input
                  value={form.ollama_url || ''}
                  onChange={e => setForm({ ...form, ollama_url: e.target.value })}
                  placeholder="http://localhost:11434"
                  data-testid="settings-ollama-host-input"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Default Model</label>
                <Input
                  value={form.ollama_model || ''}
                  onChange={e => setForm({ ...form, ollama_model: e.target.value })}
                  placeholder="tinyllama"
                />
              </div>
              {/* Health status */}
              <div className="flex items-center gap-3 p-3 bg-secondary/30 rounded-lg">
                <div className={`w-3 h-3 rounded-full ${
                  health?.ollama?.available
                    ? 'bg-[hsl(var(--status-ok))] shadow-[0_0_12px_hsl(var(--status-ok)/0.3)]'
                    : 'bg-[hsl(var(--status-err))] shadow-[0_0_12px_hsl(var(--status-err)/0.3)]'
                }`} />
                <div className="flex-1">
                  <span className="text-sm">{health?.ollama?.available ? 'Connected' : 'Not connected'}</span>
                  {health?.ollama?.models?.length > 0 && (
                    <div className="flex gap-1 mt-1">
                      {health.ollama.models.map(m => (
                        <Badge key={m} variant="outline" className="text-[10px] font-mono-ombra">{m}</Badge>
                      ))}
                    </div>
                  )}
                </div>
                <Button variant="ghost" size="sm" onClick={handleRefreshHealth}>
                  <RefreshCcw className="w-4 h-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="models" className="mt-4 space-y-4">
          <Card className="bg-card/80 backdrop-blur border-border/60">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Cloud className="w-5 h-5 text-primary" />
                Model Preferences
              </CardTitle>
              <CardDescription>Configure which models to use for different tasks</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Preferred Provider</label>
                <select
                  value={form.preferred_provider || 'auto'}
                  onChange={e => setForm({ ...form, preferred_provider: e.target.value })}
                  className="w-full h-10 px-3 rounded-md bg-secondary/60 border border-border text-sm"
                  data-testid="settings-model-preference-select"
                >
                  <option value="auto">Auto (Smart Routing)</option>
                  <option value="ollama">Ollama (Local)</option>
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="gemini">Google Gemini</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Preferred Model (optional)</label>
                <Input
                  value={form.preferred_model || ''}
                  onChange={e => setForm({ ...form, preferred_model: e.target.value })}
                  placeholder="Leave empty for default per provider"
                />
              </div>
              <div className="p-3 bg-secondary/30 rounded-lg">
                <div className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-full ${
                    health?.api_key_configured
                      ? 'bg-[hsl(var(--status-ok))] shadow-[0_0_12px_hsl(var(--status-ok)/0.3)]'
                      : 'bg-[hsl(var(--status-err))] shadow-[0_0_12px_hsl(var(--status-err)/0.3)]'
                  }`} />
                  <span className="text-sm">{health?.api_key_configured ? 'API Key Configured' : 'API Key Not Set'}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="learning" className="mt-4 space-y-4">
          <Card className="bg-card/80 backdrop-blur border-border/60">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Brain className="w-5 h-5 text-primary" />
                Learning Settings
              </CardTitle>
              <CardDescription>Control how Ombra learns from your interactions</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium">Enable Learning</label>
                  <p className="text-xs text-muted-foreground">Ombra extracts patterns and preferences from conversations</p>
                </div>
                <Switch
                  checked={form.learning_enabled ?? true}
                  onCheckedChange={v => setForm({ ...form, learning_enabled: v })}
                  data-testid="settings-learning-switch"
                />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium">White Card Mode (Default)</label>
                  <p className="text-xs text-muted-foreground">Auto-enable proactive suggestions in chat</p>
                </div>
                <Switch
                  checked={form.white_card_enabled ?? false}
                  onCheckedChange={v => setForm({ ...form, white_card_enabled: v })}
                />
              </div>
              <Separator />
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Quiet Hours Start</label>
                  <Input
                    type="time"
                    value={form.quiet_hours_start || ''}
                    onChange={e => setForm({ ...form, quiet_hours_start: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Quiet Hours End</label>
                  <Input
                    type="time"
                    value={form.quiet_hours_end || ''}
                    onChange={e => setForm({ ...form, quiet_hours_end: e.target.value })}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="telegram" className="mt-4 space-y-4">
          <Card className="bg-card/80 backdrop-blur border-border/60">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Send className="w-5 h-5 text-primary" />
                Telegram Integration
              </CardTitle>
              <CardDescription>Connect Ombra to Telegram for notifications and quick commands</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium">Enable Telegram</label>
                  <p className="text-xs text-muted-foreground">Send daily summaries and notifications</p>
                </div>
                <Switch
                  checked={form.telegram_enabled ?? false}
                  onCheckedChange={v => setForm({ ...form, telegram_enabled: v })}
                  data-testid="settings-telegram-switch"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Telegram Chat ID</label>
                <Input
                  value={form.telegram_chat_id || ''}
                  onChange={e => setForm({ ...form, telegram_chat_id: e.target.value })}
                  placeholder="Your Telegram chat ID"
                  data-testid="settings-telegram-chat-id"
                />
                <p className="text-[11px] text-muted-foreground">Send /start to @userinfobot on Telegram to get your chat ID</p>
              </div>
              <div className="flex items-center gap-3 p-3 bg-secondary/30 rounded-lg">
                <div className={`w-3 h-3 rounded-full ${
                  health?.telegram?.configured
                    ? 'bg-[hsl(var(--status-ok))] shadow-[0_0_12px_hsl(var(--status-ok)/0.3)]'
                    : 'bg-[hsl(var(--status-err))] shadow-[0_0_12px_hsl(var(--status-err)/0.3)]'
                }`} />
                <span className="text-sm">
                  {health?.telegram?.configured
                    ? `Bot connected: @${health.telegram.bot_info?.username || 'unknown'}`
                    : 'Bot not configured'}
                </span>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="email" className="mt-4 space-y-4">
          {/* Connected Provider Status */}
          <Card className="bg-card/80 backdrop-blur border-border/60">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Mail className="w-5 h-5 text-primary" />
                Email Provider
              </CardTitle>
              <CardDescription>
                Connect your email so Ombra can draft emails for you. Drafts require your approval before sending.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Active connection */}
              {emailProvider?.connected && (
                <div className="flex items-center justify-between p-3 bg-[hsl(var(--status-ok)/0.08)] border border-[hsl(var(--status-ok)/0.2)] rounded-lg">
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="w-5 h-5 text-[hsl(var(--status-ok))]" />
                    <div>
                      <span className="text-sm font-medium capitalize">{emailProvider.provider} connected</span>
                      <p className="text-xs text-muted-foreground">{emailProvider.email}</p>
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive"
                    onClick={async () => {
                      try {
                        await disconnectEmailProvider();
                        toast.success('Email disconnected');
                        loadEmailProvider();
                      } catch { toast.error('Failed to disconnect'); }
                    }}
                  >
                    <Unlink className="w-4 h-4 mr-1" /> Disconnect
                  </Button>
                </div>
              )}

              {/* Provider selection cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {[
                  { id: 'google', name: 'Google', hint: 'Gmail app password', placeholder: 'you@gmail.com',
                    icon: <svg viewBox="0 0 24 24" className="w-8 h-8" xmlns="http://www.w3.org/2000/svg"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg> },
                  { id: 'microsoft', name: 'Microsoft', hint: 'Outlook app password', placeholder: 'you@outlook.com',
                    icon: <svg viewBox="0 0 24 24" className="w-8 h-8" xmlns="http://www.w3.org/2000/svg"><rect x="1" y="1" width="10" height="10" fill="#F25022"/><rect x="13" y="1" width="10" height="10" fill="#7FBA00"/><rect x="1" y="13" width="10" height="10" fill="#00A4EF"/><rect x="13" y="13" width="10" height="10" fill="#FFB900"/></svg> },
                  { id: 'icloud', name: 'iCloud', hint: 'iCloud app password', placeholder: 'you@icloud.com',
                    icon: <svg viewBox="0 0 24 24" className="w-8 h-8" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M18.5 10.5c-.17 0-.34.01-.5.04C17.58 7.55 15.03 5.5 12 5.5c-2.42 0-4.51 1.28-5.58 3.18C4.24 9.05 2.5 10.97 2.5 13.25 2.5 15.87 4.63 18 7.25 18h11.25c2.07 0 3.75-1.68 3.75-3.75S20.57 10.5 18.5 10.5z" fill="#A2AAAD"/></svg> },
                ].map(p => (
                  <button key={p.id}
                    onClick={() => setProviderForm({ ...providerForm, provider: p.id, email: '', app_password: '' })}
                    className={`relative flex flex-col items-center gap-2 p-4 rounded-xl border transition-all duration-200
                      ${emailProvider?.provider === p.id && emailProvider?.connected
                        ? 'border-[hsl(var(--status-ok)/0.4)] bg-[hsl(var(--status-ok)/0.05)]'
                        : providerForm.provider === p.id
                          ? 'border-primary/60 bg-primary/5 ring-1 ring-primary/20'
                          : 'border-border/60 bg-secondary/20 hover:bg-secondary/40 hover:border-border cursor-pointer'}
                    `}
                  >
                    {p.icon}
                    <span className="text-sm font-medium">{p.name}</span>
                    {emailProvider?.provider === p.id && emailProvider?.connected && (
                      <Badge variant="outline" className="text-[10px] text-[hsl(var(--status-ok))] border-[hsl(var(--status-ok)/0.3)]">Connected</Badge>
                    )}
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Connect Form (shown when a provider is selected) */}
          {providerForm.provider && !emailProvider?.connected && (
            <Card className="bg-card/80 backdrop-blur border-border/60">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <KeyRound className="w-5 h-5 text-primary" />
                  Connect {providerForm.provider === 'google' ? 'Google' : providerForm.provider === 'microsoft' ? 'Microsoft' : 'iCloud'}
                </CardTitle>
                <CardDescription>
                  {providerForm.provider === 'google' && 'Go to Google Account → Security → 2-Step Verification → App Passwords to generate one'}
                  {providerForm.provider === 'microsoft' && 'Go to Microsoft Account → Security → Advanced security → App Passwords'}
                  {providerForm.provider === 'icloud' && 'Go to appleid.apple.com → Sign-In and Security → App-Specific Passwords'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Email</label>
                  <Input
                    value={providerForm.email}
                    onChange={e => setProviderForm({ ...providerForm, email: e.target.value })}
                    placeholder={providerForm.provider === 'google' ? 'you@gmail.com' : providerForm.provider === 'microsoft' ? 'you@outlook.com' : 'you@icloud.com'}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">App Password</label>
                  <Input
                    type="password"
                    value={providerForm.app_password}
                    onChange={e => setProviderForm({ ...providerForm, app_password: e.target.value })}
                    placeholder="xxxx-xxxx-xxxx-xxxx"
                    autoComplete="new-password"
                  />
                </div>
                <Button variant="outline" size="sm" onClick={async () => {
                  try {
                    const res = await connectEmailProvider(providerForm.provider, providerForm.email, providerForm.app_password);
                    if (res.success) {
                      toast.success(`${providerForm.provider} connected!`);
                      loadEmailProvider();
                      setProviderForm({ email: '', app_password: '' });
                    } else toast.error(res.error || 'Connection failed');
                  } catch { toast.error('Could not reach server'); }
                }}>
                  <Link2 className="w-4 h-4 mr-2" /> Connect & Verify
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Test email */}
          {emailProvider?.connected && (
            <Card className="bg-card/80 backdrop-blur border-border/60">
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <Button variant="outline" size="sm" onClick={async () => {
                    try {
                      const res = await testEmail();
                      if (res.success) toast.success(res.message || 'Test email sent!');
                      else toast.error(res.error || 'Test failed');
                    } catch { toast.error('Could not reach server'); }
                  }}>
                    <Mail className="w-4 h-4 mr-2" /> Send Test Email
                  </Button>
                  <span className="text-[11px] text-muted-foreground">Sends a test email to your connected address to verify everything works</span>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving} data-testid="settings-save-button">
          {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
          Save Settings
        </Button>
      </div>
    </div>
  );
}

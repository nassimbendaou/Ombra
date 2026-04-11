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
  Save, RefreshCcw, Loader2, CheckCircle2, AlertCircle, Send
} from 'lucide-react';
import { getSettings, updateSettings, getHealth, testTelegram, sendTelegramMessage, getLearningMetrics } from '../lib/api';
import { toast } from 'sonner';

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({});

  useEffect(() => {
    Promise.all([
      getSettings().catch(() => null),
      getHealth().catch(() => null)
    ]).then(([s, h]) => {
      setSettings(s);
      setHealth(h);
      if (s) setForm(s);
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

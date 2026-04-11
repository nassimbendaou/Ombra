import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Separator } from '../components/ui/separator';
import { Progress } from '../components/ui/progress';
import {
  Zap, MessageSquare, Terminal, Brain, Activity, Clock,
  TrendingUp, ArrowRight, CheckCircle2, Circle, Sparkles,
  Cpu, Cloud, Database, WifiOff, Bot, Play, Pause, Square, RefreshCw
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getDashboardSummary, getSystemStatus, getTasks, getActivity, getWhiteCardSuggestions, getAutonomyStatus, pauseAutonomy, resumeAutonomy, stopAutonomy } from '../lib/api';
import ActivityItem from '../components/ActivityItem';

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [status, setStatus] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [recentActivity, setRecentActivity] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [autonomyStatus, setAutonomyStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autonomyActionLoading, setAutonomyActionLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([
      getDashboardSummary().catch(() => null),
      getSystemStatus().catch(() => null),
      getTasks().catch(() => []),
      getActivity(null, 5).catch(() => ({ activities: [] })),
      getWhiteCardSuggestions().catch(() => ({ suggestions: [] })),
      getAutonomyStatus().catch(() => null)
    ]).then(([s, st, t, a, wc, auto]) => {
      setSummary(s);
      setStatus(st);
      setTasks(t || []);
      setRecentActivity(a?.activities || []);
      setSuggestions(wc?.suggestions || []);
      setAutonomyStatus(auto);
      setLoading(false);
    });
  }, []);

  const handlePauseAutonomy = async () => {
    setAutonomyActionLoading(true);
    try {
      await pauseAutonomy();
      const newStatus = await getAutonomyStatus();
      setAutonomyStatus(newStatus);
    } catch (error) {
      console.error('Failed to pause autonomy:', error);
    } finally {
      setAutonomyActionLoading(false);
    }
  };

  const handleResumeAutonomy = async () => {
    setAutonomyActionLoading(true);
    try {
      await resumeAutonomy();
      const newStatus = await getAutonomyStatus();
      setAutonomyStatus(newStatus);
    } catch (error) {
      console.error('Failed to resume autonomy:', error);
    } finally {
      setAutonomyActionLoading(false);
    }
  };

  const handleStopAutonomy = async () => {
    setAutonomyActionLoading(true);
    try {
      await stopAutonomy();
      const newStatus = await getAutonomyStatus();
      setAutonomyStatus(newStatus);
    } catch (error) {
      console.error('Failed to stop autonomy:', error);
    } finally {
      setAutonomyActionLoading(false);
    }
  };

  const statusItems = status ? [
    { label: 'Ollama', status: status.ollama?.status, icon: Cpu, detail: status.ollama?.models?.join(', ') || 'No models' },
    { label: 'Cloud API', status: status.cloud_api?.status === 'configured' ? 'online' : 'offline', icon: Cloud, detail: status.cloud_api?.status },
    { label: 'Memory', status: status.memory?.status, icon: Database, detail: `${status.memory?.memories || 0} memories` },
    { label: 'Agents', status: 'online', icon: Bot, detail: `${status.agents?.count || 0} agents` },
    { label: 'K1 Learning', status: (status.k1?.distillations || 0) > 0 ? 'active' : 'idle', icon: Brain, detail: `${status.k1?.distillations || 0} distillations` },
    { label: 'Autonomy', status: autonomyStatus?.running ? (autonomyStatus?.paused ? 'idle' : 'active') : 'offline', icon: Sparkles, detail: `${autonomyStatus?.stats?.ticks || 0} ticks, ${autonomyStatus?.stats?.ideas_generated || 0} ideas` },
    { label: 'Telegram', status: status.telegram?.configured ? 'online' : 'offline', icon: MessageSquare, detail: status.telegram?.configured ? 'Connected' : 'Not set' },
  ] : [];

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-secondary/60 rounded animate-pulse" />
        <div className="grid grid-cols-12 gap-4 lg:gap-6">
          <div className="col-span-12 lg:col-span-8 h-48 bg-card/40 rounded-xl animate-pulse" />
          <div className="col-span-12 lg:col-span-4 h-48 bg-card/40 rounded-xl animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight" data-testid="dashboard-title">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">Overview of Ombra's daily activity and system status</p>
      </div>

      {/* Row 1: Summary + Status */}
      <div className="grid grid-cols-12 gap-4 lg:gap-6">
        {/* Daily Summary Card */}
        <Card className="col-span-12 lg:col-span-8 bg-card/80 backdrop-blur border-border/60 transition-colors duration-200 hover:border-border/80 hover:shadow-[0_0_0_1px_hsl(var(--border)/0.6),0_0_24px_hsl(var(--primary)/0.12)]" data-testid="dashboard-daily-summary-card">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="w-5 h-5 text-primary" />
                  Daily Summary
                </CardTitle>
                <CardDescription className="font-mono-ombra text-xs mt-1">{summary?.date}</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="dashboard-daily-summary-stats">
              <div className="space-y-1">
                <div className="text-2xl font-semibold">{summary?.total_interactions || 0}</div>
                <div className="text-xs text-muted-foreground flex items-center gap-1">
                  <MessageSquare className="w-3 h-3" /> Interactions
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-2xl font-semibold">{summary?.tool_executions || 0}</div>
                <div className="text-xs text-muted-foreground flex items-center gap-1">
                  <Terminal className="w-3 h-3" /> Tool Runs
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-2xl font-semibold">{summary?.memory_operations || 0}</div>
                <div className="text-xs text-muted-foreground flex items-center gap-1">
                  <Brain className="w-3 h-3" /> Memory Ops
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-2xl font-semibold font-mono-ombra">{summary?.avg_response_ms || 0}<span className="text-sm text-muted-foreground">ms</span></div>
                <div className="text-xs text-muted-foreground flex items-center gap-1">
                  <Clock className="w-3 h-3" /> Avg Response
                </div>
              </div>
            </div>
            <Separator className="my-4" />
            <p className="text-sm text-muted-foreground" data-testid="dashboard-daily-summary-text">{summary?.summary || 'No activity today yet. Start chatting to see your summary!'}</p>
            {summary?.providers_used && Object.keys(summary.providers_used).length > 0 && (
              <div className="mt-3 flex items-center gap-2 flex-wrap">
                <span className="text-xs text-muted-foreground">Providers:</span>
                {Object.entries(summary.providers_used).map(([provider, count]) => (
                  <Badge key={provider} variant="outline" className="font-mono-ombra text-[10px]">
                    {provider}: {count}
                  </Badge>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* System Status Panel */}
        <Card className="col-span-12 lg:col-span-4 bg-card/80 backdrop-blur border-border/60" data-testid="dashboard-system-status-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Zap className="w-5 h-5 text-primary" />
              System Status
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {statusItems.map((item) => (
              <div key={item.label} className="flex items-center justify-between" data-testid={`system-status-${item.label.toLowerCase().replace(' ', '-')}`}>
                <div className="flex items-center gap-2">
                  <div className={`w-2.5 h-2.5 rounded-full ${
                    item.status === 'online' || item.status === 'active'
                      ? 'bg-[hsl(var(--status-ok))] shadow-[0_0_18px_hsl(var(--status-ok)/0.35)]'
                      : item.status === 'idle' || item.status === 'configured'
                        ? 'bg-[hsl(var(--status-info))] shadow-[0_0_18px_hsl(var(--status-info)/0.35)]'
                        : 'bg-[hsl(var(--status-err))] shadow-[0_0_12px_hsl(var(--status-err)/0.25)]'
                  }`} />
                  <item.icon className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm">{item.label}</span>
                </div>
                <span className="text-xs text-muted-foreground font-mono-ombra">{item.detail}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Row 1.5: Autonomy Control */}
      {autonomyStatus && (
        <Card className="bg-card/80 backdrop-blur border-border/60" data-testid="dashboard-autonomy-control-card">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Sparkles className="w-5 h-5 text-[hsl(var(--activity-autonomy))]" />
                  Autonomy Daemon
                </CardTitle>
                <CardDescription className="text-xs mt-1">
                  Background autonomous execution engine
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                {autonomyStatus.running && !autonomyStatus.paused && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handlePauseAutonomy}
                    disabled={autonomyActionLoading}
                    data-testid="autonomy-pause-button"
                    className="gap-1.5"
                  >
                    <Pause className="w-3.5 h-3.5" />
                    Pause
                  </Button>
                )}
                {autonomyStatus.running && autonomyStatus.paused && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleResumeAutonomy}
                    disabled={autonomyActionLoading}
                    data-testid="autonomy-resume-button"
                    className="gap-1.5"
                  >
                    <Play className="w-3.5 h-3.5" />
                    Resume
                  </Button>
                )}
                {autonomyStatus.running && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleStopAutonomy}
                    disabled={autonomyActionLoading}
                    data-testid="autonomy-stop-button"
                    className="gap-1.5 hover:border-destructive/50 hover:text-destructive"
                  >
                    <Square className="w-3.5 h-3.5" />
                    Stop
                  </Button>
                )}
                <div className={`px-2.5 py-1 rounded-md text-xs font-medium flex items-center gap-1.5 ${
                  autonomyStatus.running && !autonomyStatus.paused
                    ? 'bg-[hsl(var(--status-ok)/0.15)] text-[hsl(var(--status-ok))] border border-[hsl(var(--status-ok)/0.3)]'
                    : autonomyStatus.running && autonomyStatus.paused
                      ? 'bg-[hsl(var(--status-info)/0.15)] text-[hsl(var(--status-info))] border border-[hsl(var(--status-info)/0.3)]'
                      : 'bg-secondary/50 text-muted-foreground border border-border'
                }`} data-testid="autonomy-status-badge">
                  <div className={`w-1.5 h-1.5 rounded-full ${
                    autonomyStatus.running && !autonomyStatus.paused
                      ? 'bg-[hsl(var(--status-ok))] animate-ombra-pulse'
                      : autonomyStatus.running && autonomyStatus.paused
                        ? 'bg-[hsl(var(--status-info))]'
                        : 'bg-muted-foreground/40'
                  }`} />
                  {autonomyStatus.running && !autonomyStatus.paused ? 'Running' : autonomyStatus.running && autonomyStatus.paused ? 'Paused' : 'Stopped'}
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="space-y-1">
                <div className="text-lg font-semibold font-mono-ombra">{autonomyStatus.stats?.ticks || 0}</div>
                <div className="text-xs text-muted-foreground flex items-center gap-1">
                  <RefreshCw className="w-3 h-3" /> Total Ticks
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-lg font-semibold font-mono-ombra">{autonomyStatus.stats?.ideas_generated || 0}</div>
                <div className="text-xs text-muted-foreground flex items-center gap-1">
                  <Sparkles className="w-3 h-3" /> Ideas Generated
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-lg font-semibold font-mono-ombra">{autonomyStatus.stats?.decay_runs || 0}</div>
                <div className="text-xs text-muted-foreground flex items-center gap-1">
                  <Database className="w-3 h-3" /> Memory Decay Runs
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-lg font-semibold font-mono-ombra">{autonomyStatus.stats?.telegram_sent || 0}</div>
                <div className="text-xs text-muted-foreground flex items-center gap-1">
                  <MessageSquare className="w-3 h-3" /> Telegram Summaries
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-lg font-semibold font-mono-ombra">{autonomyStatus.stats?.cloud_escalations || 0}</div>
                <div className="text-xs text-muted-foreground flex items-center gap-1">
                  <Cloud className="w-3 h-3" /> Cloud Escalations
                </div>
              </div>
            </div>
            {autonomyStatus.quiet_hours_active && (
              <div className="mt-4 p-2 rounded-lg bg-secondary/30 border border-border/40">
                <p className="text-xs text-muted-foreground flex items-center gap-1.5">
                  <Clock className="w-3 h-3" />
                  Quiet hours active - daemon operating in low-activity mode
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Row 2: Tasks + Suggestions */}
      <div className="grid grid-cols-12 gap-4 lg:gap-6">
        {/* Current Tasks */}
        <Card className="col-span-12 lg:col-span-6 bg-card/80 backdrop-blur border-border/60" data-testid="dashboard-current-tasks-card">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-base">
                <CheckCircle2 className="w-5 h-5 text-[hsl(var(--activity-tool))]" />
                Current Tasks
              </CardTitle>
              <Button variant="ghost" size="sm" onClick={() => navigate('/chat')} className="text-xs">
                New Task <ArrowRight className="w-3 h-3 ml-1" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {tasks.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground">
                <Circle className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">No active tasks. Ask Ombra to create one!</p>
              </div>
            ) : (
              <div className="space-y-2">
                {tasks.slice(0, 5).map((task) => (
                  <div key={task._id} className="flex items-center justify-between p-2 rounded-lg bg-secondary/30 hover:bg-secondary/50 transition-colors" data-testid="task-row">
                    <div className="flex items-center gap-2 min-w-0">
                      <div className={`w-2 h-2 rounded-full ${
                        task.status === 'completed' ? 'bg-[hsl(var(--status-ok))]'
                        : task.status === 'in_progress' ? 'bg-[hsl(var(--status-info))] animate-ombra-pulse'
                        : 'bg-muted-foreground/40'
                      }`} />
                      <span className="text-sm truncate">{task.title}</span>
                    </div>
                    <Badge variant="outline" className="text-[10px] font-mono-ombra">{task.status}</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* White Card Suggestions */}
        <Card className="col-span-12 lg:col-span-6 bg-card/80 backdrop-blur border-border/60">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="w-5 h-5 text-[hsl(var(--activity-autonomy))]" />
              Suggestions
            </CardTitle>
            <CardDescription>Proactive ideas from Ombra</CardDescription>
          </CardHeader>
          <CardContent>
            {suggestions.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground">
                <Sparkles className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">Start chatting and I'll suggest ideas.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {suggestions.map((s, i) => (
                  <div key={i} className="p-3 rounded-lg bg-secondary/30 hover:bg-secondary/50 transition-colors cursor-pointer" onClick={() => navigate('/chat')}>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-[10px]">{s.type}</Badge>
                      <span className="text-sm font-medium">{s.title}</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">{s.description}</p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Row 3: Recent Activity */}
      <Card className="bg-card/80 backdrop-blur border-border/60">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="w-5 h-5 text-primary" />
              Recent Activity
            </CardTitle>
            <Button variant="ghost" size="sm" onClick={() => navigate('/activity')} className="text-xs">
              View All <ArrowRight className="w-3 h-3 ml-1" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {recentActivity.length === 0 ? (
            <div className="text-center py-6 text-muted-foreground">
              <Activity className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">No activity yet today. Run a task to start logging activity.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {recentActivity.map((a, i) => (
                <ActivityItem key={a._id || i} activity={a} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Progress } from '../components/ui/progress';
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import {
  Activity, Zap, Brain, Database, TrendingUp, Clock,
  Server, RefreshCw, Sparkles, Terminal, Target
} from 'lucide-react';
import {
  getAnalyticsOverview,
  getAnalyticsAutonomy,
  getAnalyticsTasks,
  getAnalyticsTools,
  getAnalyticsMemory,
  getAnalyticsProviders
} from '../lib/api';

export default function Analytics() {
  const [overview, setOverview] = useState(null);
  const [autonomy, setAutonomy] = useState(null);
  const [tasks, setTasks] = useState(null);
  const [tools, setTools] = useState(null);
  const [memory, setMemory] = useState(null);
  const [providers, setProviders] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadData = async () => {
    try {
      const [overviewData, autonomyData, tasksData, toolsData, memoryData, providersData] = await Promise.all([
        getAnalyticsOverview(),
        getAnalyticsAutonomy(),
        getAnalyticsTasks(),
        getAnalyticsTools(),
        getAnalyticsMemory(),
        getAnalyticsProviders()
      ]);
      
      setOverview(overviewData);
      setAutonomy(autonomyData);
      setTasks(tasksData);
      setTools(toolsData);
      setMemory(memoryData);
      setProviders(providersData);
      setLoading(false);
    } catch (error) {
      console.error('Failed to load analytics:', error);
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        loadData();
      }, 10000); // Refresh every 10 seconds
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-secondary/60 rounded animate-pulse" />
        <div className="grid grid-cols-12 gap-4 lg:gap-6">
          <div className="col-span-12 h-48 bg-card/40 rounded-xl animate-pulse" />
        </div>
      </div>
    );
  }

  const CHART_COLORS = ['hsl(var(--chart-1))', 'hsl(var(--chart-2))', 'hsl(var(--chart-3))', 'hsl(var(--chart-4))', 'hsl(var(--chart-5))'];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight" data-testid="analytics-title">Analytics</h1>
          <p className="text-sm text-muted-foreground mt-1">System performance and operational insights</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={autoRefresh ? "default" : "outline"} className="font-mono text-xs">
            <RefreshCw className={`w-3 h-3 mr-1 ${autoRefresh ? 'animate-spin' : ''}`} />
            Auto-refresh: {autoRefresh ? 'ON' : 'OFF'}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAutoRefresh(!autoRefresh)}
            data-testid="analytics-auto-refresh-toggle"
          >
            {autoRefresh ? 'Pause' : 'Resume'}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={loadData}
            data-testid="analytics-refresh-button"
          >
            <RefreshCw className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Overview KPIs */}
      {overview && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="bg-card/80 backdrop-blur border-border/60">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-2xl font-semibold font-mono">{overview.activities.total}</div>
                  <div className="text-xs text-muted-foreground mt-1">Activities (24h)</div>
                </div>
                <Activity className="w-8 h-8 text-[hsl(var(--activity-model))] opacity-60" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card/80 backdrop-blur border-border/60">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-2xl font-semibold font-mono">{overview.tasks.completed_24h}</div>
                  <div className="text-xs text-muted-foreground mt-1">Tasks Completed</div>
                </div>
                <Target className="w-8 h-8 text-[hsl(var(--activity-tool))] opacity-60" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card/80 backdrop-blur border-border/60">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-2xl font-semibold font-mono">{overview.tasks.success_rate}%</div>
                  <div className="text-xs text-muted-foreground mt-1">Success Rate</div>
                </div>
                <TrendingUp className="w-8 h-8 text-[hsl(var(--status-ok))] opacity-60" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card/80 backdrop-blur border-border/60">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-2xl font-semibold font-mono">{overview.memory.total}</div>
                  <div className="text-xs text-muted-foreground mt-1">Total Memories</div>
                </div>
                <Database className="w-8 h-8 text-[hsl(var(--activity-memory))] opacity-60" />
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Detailed Analytics Tabs */}
      <Tabs defaultValue="tasks" className="space-y-4">
        <TabsList className="bg-secondary/60">
          <TabsTrigger value="tasks" data-testid="analytics-tab-tasks">Tasks</TabsTrigger>
          <TabsTrigger value="providers" data-testid="analytics-tab-providers">Providers</TabsTrigger>
          <TabsTrigger value="autonomy" data-testid="analytics-tab-autonomy">Autonomy</TabsTrigger>
          <TabsTrigger value="tools" data-testid="analytics-tab-tools">Tools</TabsTrigger>
          <TabsTrigger value="memory" data-testid="analytics-tab-memory">Memory</TabsTrigger>
        </TabsList>

        {/* Tasks Tab */}
        <TabsContent value="tasks" className="space-y-4">
          {tasks && (
            <div className="grid grid-cols-12 gap-4 lg:gap-6">
              {/* Status Breakdown */}
              <Card className="col-span-12 lg:col-span-6 bg-card/80 backdrop-blur border-border/60">
                <CardHeader>
                  <CardTitle className="text-base">Task Status Distribution</CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={240}>
                    <PieChart>
                      <Pie
                        data={Object.entries(tasks.status_breakdown || {}).map(([status, count]) => ({
                          name: status,
                          value: count
                        }))}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {Object.keys(tasks.status_breakdown || {}).map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              {/* Execution Stats */}
              <Card className="col-span-12 lg:col-span-6 bg-card/80 backdrop-blur border-border/60">
                <CardHeader>
                  <CardTitle className="text-base">Execution Performance</CardTitle>
                  <CardDescription>Last 7 days</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {tasks.duration_stats && tasks.duration_stats.avg_duration_ms && (
                    <>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-muted-foreground">Avg Duration</span>
                          <span className="font-mono font-semibold">{Math.round(tasks.duration_stats.avg_duration_ms)}ms</span>
                        </div>
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-muted-foreground">Min Duration</span>
                          <span className="font-mono">{Math.round(tasks.duration_stats.min_duration_ms)}ms</span>
                        </div>
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-muted-foreground">Max Duration</span>
                          <span className="font-mono">{Math.round(tasks.duration_stats.max_duration_ms)}ms</span>
                        </div>
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-muted-foreground">Total Tasks</span>
                          <span className="font-mono font-semibold">{tasks.duration_stats.total_tasks}</span>
                        </div>
                      </div>
                      <div className="space-y-2">
                        <div className="text-sm text-muted-foreground">Scheduled Tasks</div>
                        <div className="text-2xl font-semibold font-mono">{tasks.scheduled_tasks}</div>
                      </div>
                    </>
                  )}
                  {tasks.queue_status && (
                    <div className="space-y-2 pt-4 border-t border-border/40">
                      <div className="text-sm font-semibold">Queue Status</div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Queue Size</span>
                        <span className="font-mono">{tasks.queue_status.queue_size}</span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Active Workers</span>
                        <span className="font-mono">{tasks.queue_status.active_workers}</span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Max Concurrency</span>
                        <span className="font-mono">{tasks.queue_status.max_concurrency}</span>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* Providers Tab */}
        <TabsContent value="providers" className="space-y-4">
          {providers && providers.providers && (
            <div className="grid grid-cols-12 gap-4 lg:gap-6">
              <Card className="col-span-12 bg-card/80 backdrop-blur border-border/60">
                <CardHeader>
                  <CardTitle className="text-base">Provider Performance (24h)</CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={providers.providers}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
                      <XAxis dataKey="_id" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                      <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))' }}
                        labelStyle={{ color: 'hsl(var(--foreground))' }}
                      />
                      <Legend />
                      <Bar dataKey="count" fill="hsl(var(--chart-1))" name="Requests" />
                      <Bar dataKey="avg_duration_ms" fill="hsl(var(--chart-2))" name="Avg Latency (ms)" />
                    </BarChart>
                  </ResponsiveContainer>

                  <div className="mt-4 space-y-2">
                    {providers.providers.map((provider, idx) => (
                      <div key={idx} className="flex items-center justify-between p-2 rounded-lg bg-secondary/30">
                        <div className="flex items-center gap-3">
                          <Server className="w-4 h-4 text-muted-foreground" />
                          <span className="text-sm font-medium">{provider._id}</span>
                        </div>
                        <div className="flex items-center gap-4 text-xs font-mono">
                          <span className="text-muted-foreground">{provider.count} calls</span>
                          <span className="text-muted-foreground">{Math.round(provider.avg_duration_ms)}ms avg</span>
                          <Badge variant={provider.error_rate > 5 ? "destructive" : "outline"} className="text-[10px]">
                            {provider.error_rate}% errors
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* Autonomy Tab */}
        <TabsContent value="autonomy" className="space-y-4">
          {autonomy && (
            <div className="grid grid-cols-12 gap-4 lg:gap-6">
              <Card className="col-span-12 lg:col-span-6 bg-card/80 backdrop-blur border-border/60">
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-[hsl(var(--activity-autonomy))]" />
                    Daemon Statistics
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Status</span>
                    <Badge variant={autonomy.running ? "default" : "outline"}>
                      {autonomy.running && !autonomy.paused ? 'Running' : autonomy.paused ? 'Paused' : 'Stopped'}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Total Ticks</span>
                    <span className="font-mono font-semibold">{autonomy.stats?.ticks || 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Ideas Generated</span>
                    <span className="font-mono">{autonomy.stats?.ideas_generated || 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Memory Decay Runs</span>
                    <span className="font-mono">{autonomy.stats?.decay_runs || 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Telegram Summaries</span>
                    <span className="font-mono">{autonomy.stats?.telegram_sent || 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Cloud Escalations</span>
                    <span className="font-mono">{autonomy.stats?.cloud_escalations || 0}</span>
                  </div>
                </CardContent>
              </Card>

              <Card className="col-span-12 lg:col-span-6 bg-card/80 backdrop-blur border-border/60">
                <CardHeader>
                  <CardTitle className="text-base">Recent Activity</CardTitle>
                  <CardDescription>Last 24 hours</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Autonomy Events</span>
                      <span className="font-mono text-2xl font-semibold">{autonomy.recent_activities || 0}</span>
                    </div>
                    {autonomy.quiet_hours_active && (
                      <div className="mt-4 p-3 rounded-lg bg-secondary/30 border border-border/40">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <Clock className="w-3 h-3" />
                          Quiet hours currently active
                        </div>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* Tools Tab */}
        <TabsContent value="tools" className="space-y-4">
          {tools && (
            <div className="grid grid-cols-12 gap-4 lg:gap-6">
              <Card className="col-span-12 bg-card/80 backdrop-blur border-border/60">
                <CardHeader>
                  <CardTitle className="text-base">Tool Usage (24h)</CardTitle>
                </CardHeader>
                <CardContent>
                  {tools.tool_usage && tools.tool_usage.length > 0 ? (
                    <>
                      <ResponsiveContainer width="100%" height={240}>
                        <BarChart data={tools.tool_usage}>
                          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
                          <XAxis dataKey="_id" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                          <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                          <Tooltip 
                            contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))' }}
                          />
                          <Bar dataKey="count" fill="hsl(var(--activity-tool))" name="Executions" />
                        </BarChart>
                      </ResponsiveContainer>

                      <div className="mt-4 p-3 rounded-lg bg-secondary/30 border border-border/40">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Terminal className="w-4 h-4 text-destructive" />
                            <span className="text-sm font-medium">Blocked Commands</span>
                          </div>
                          <Badge variant="destructive" className="font-mono">
                            {tools.blocked_commands_24h}
                          </Badge>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <Terminal className="w-12 h-12 mx-auto mb-2 opacity-30" />
                      <p className="text-sm">No tool usage in the last 24 hours</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* Memory Tab */}
        <TabsContent value="memory" className="space-y-4">
          {memory && (
            <div className="grid grid-cols-12 gap-4 lg:gap-6">
              <Card className="col-span-12 lg:col-span-6 bg-card/80 backdrop-blur border-border/60">
                <CardHeader>
                  <CardTitle className="text-base">Memory Type Distribution</CardTitle>
                </CardHeader>
                <CardContent>
                  {memory.type_breakdown && memory.type_breakdown.length > 0 ? (
                    <ResponsiveContainer width="100%" height={240}>
                      <PieChart>
                        <Pie
                          data={memory.type_breakdown.map(item => ({
                            name: item._id,
                            value: item.count,
                            avgScore: item.avg_score
                          }))}
                          cx="50%"
                          cy="50%"
                          labelLine={false}
                          label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                          outerRadius={80}
                          fill="#8884d8"
                          dataKey="value"
                        >
                          {memory.type_breakdown.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <Database className="w-12 h-12 mx-auto mb-2 opacity-30" />
                      <p className="text-sm">No memory data available</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="col-span-12 lg:col-span-6 bg-card/80 backdrop-blur border-border/60">
                <CardHeader>
                  <CardTitle className="text-base">Memory Statistics</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Total Memories</span>
                    <span className="font-mono font-semibold text-xl">{memory.total_memories}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Pinned Memories</span>
                    <span className="font-mono">{memory.pinned_memories}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Decayed (24h)</span>
                    <span className="font-mono">{memory.decayed_24h || 0}</span>
                  </div>
                  
                  {memory.score_distribution && memory.score_distribution.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-border/40 space-y-2">
                      <div className="text-sm font-semibold mb-2">Utility Score Distribution</div>
                      {memory.score_distribution.map((bucket, idx) => (
                        <div key={idx} className="space-y-1">
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-muted-foreground">
                              {bucket._id === "other" ? "Other" : `${bucket._id}-${(bucket._id + 0.25).toFixed(2)}`}
                            </span>
                            <span className="font-mono">{bucket.count}</span>
                          </div>
                          <Progress value={(bucket.count / memory.total_memories) * 100} className="h-1.5" />
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

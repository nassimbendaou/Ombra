import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Activity, Filter, RefreshCcw, Loader2 } from 'lucide-react';
import ActivityItem from '../components/ActivityItem';
import { getActivity, getActivitySummary } from '../lib/api';

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'model_call', label: 'Model' },
  { value: 'tool_execution', label: 'Tool' },
  { value: 'memory_write', label: 'Memory' },
  { value: 'autonomy', label: 'Autonomy' },
  { value: 'permission_change', label: 'Permission' },
  { value: 'system', label: 'System' },
];

export default function ActivityTimeline() {
  const [activities, setActivities] = useState([]);
  const [filter, setFilter] = useState('all');
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);

  const fetchActivities = async (type) => {
    setLoading(true);
    try {
      const [data, sum] = await Promise.all([
        getActivity(type, 100),
        getActivitySummary()
      ]);
      setActivities(data.activities || []);
      setTotal(data.total || 0);
      setSummary(sum);
    } catch (e) {
      console.error('Failed to load activity', e);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchActivities(filter);
  }, [filter]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Activity Timeline</h1>
          <p className="text-sm text-muted-foreground mt-1">Everything Ombra has done, fully transparent</p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => fetchActivities(filter)}>
          <RefreshCcw className={`w-4 h-4 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </Button>
      </div>

      {/* Summary */}
      {summary && (
        <Card className="bg-card/80 backdrop-blur border-border/60">
          <CardContent className="py-3 px-4">
            <div className="flex items-center gap-6 flex-wrap">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium">{summary.total} events today</span>
              </div>
              {summary.by_type && Object.entries(summary.by_type).map(([type, count]) => (
                <div key={type} className="flex items-center gap-1">
                  <Badge variant="outline" className="text-[10px] font-mono-ombra">{type}</Badge>
                  <span className="text-xs text-muted-foreground">{count}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap" data-testid="activity-filter-toggle-group">
        <Filter className="w-4 h-4 text-muted-foreground" />
        {FILTERS.map(f => (
          <Button
            key={f.value}
            variant={filter === f.value ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter(f.value)}
            className="text-xs h-8"
          >
            {f.label}
            {filter === f.value && total > 0 && (
              <Badge variant="secondary" className="ml-1 text-[10px]">{total}</Badge>
            )}
          </Button>
        ))}
      </div>

      {/* Timeline */}
      <div className="space-y-2" data-testid="activity-timeline-list">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : activities.length === 0 ? (
          <Card className="bg-card/40 border-border/40">
            <CardContent className="py-12 text-center">
              <Activity className="w-10 h-10 mx-auto mb-3 text-muted-foreground/30" />
              <p className="text-sm text-muted-foreground">No activity yet. Run a task to start logging activity.</p>
            </CardContent>
          </Card>
        ) : (
          activities.map((a, i) => (
            <ActivityItem key={a._id || i} activity={a} />
          ))
        )}
      </div>
    </div>
  );
}

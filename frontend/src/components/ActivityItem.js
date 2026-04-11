import React from 'react';
import { motion } from 'framer-motion';
import { Badge } from './ui/badge';
import {
  Cpu, Wrench, Brain, Sparkles, Clock, ChevronDown, ChevronUp, Settings
} from 'lucide-react';
import { useState } from 'react';

const typeConfig = {
  model_call: {
    icon: Cpu,
    label: 'Model Call',
    borderColor: 'border-l-[hsl(var(--activity-model))]',
    badgeColor: 'bg-[hsl(var(--activity-model)/0.15)] text-[hsl(var(--activity-model))] border-[hsl(var(--activity-model)/0.3)]',
  },
  tool_execution: {
    icon: Wrench,
    label: 'Tool',
    borderColor: 'border-l-[hsl(var(--activity-tool))]',
    badgeColor: 'bg-[hsl(var(--activity-tool)/0.15)] text-[hsl(var(--activity-tool))] border-[hsl(var(--activity-tool)/0.3)]',
  },
  memory_write: {
    icon: Brain,
    label: 'Memory',
    borderColor: 'border-l-[hsl(var(--activity-memory))]',
    badgeColor: 'bg-[hsl(var(--activity-memory)/0.15)] text-[hsl(var(--activity-memory))] border-[hsl(var(--activity-memory)/0.3)]',
  },
  memory_read: {
    icon: Brain,
    label: 'Memory',
    borderColor: 'border-l-[hsl(var(--activity-memory))]',
    badgeColor: 'bg-[hsl(var(--activity-memory)/0.15)] text-[hsl(var(--activity-memory))] border-[hsl(var(--activity-memory)/0.3)]',
  },
  memory_decay: {
    icon: Brain,
    label: 'Memory Decay',
    borderColor: 'border-l-[hsl(var(--activity-memory))]',
    badgeColor: 'bg-[hsl(var(--activity-memory)/0.15)] text-[hsl(var(--activity-memory))] border-[hsl(var(--activity-memory)/0.3)]',
  },
  autonomy: {
    icon: Sparkles,
    label: 'Autonomy',
    borderColor: 'border-l-[hsl(var(--activity-autonomy))]',
    badgeColor: 'bg-[hsl(var(--activity-autonomy)/0.15)] text-[hsl(var(--activity-autonomy))] border-[hsl(var(--activity-autonomy)/0.3)]',
  },
  agent_execution: {
    icon: Sparkles,
    label: 'Agent',
    borderColor: 'border-l-[hsl(var(--activity-autonomy))]',
    badgeColor: 'bg-[hsl(var(--activity-autonomy)/0.15)] text-[hsl(var(--activity-autonomy))] border-[hsl(var(--activity-autonomy)/0.3)]',
  },
  k1_learning: {
    icon: Brain,
    label: 'K1 Learning',
    borderColor: 'border-l-[hsl(var(--activity-autonomy))]',
    badgeColor: 'bg-[hsl(var(--activity-autonomy)/0.15)] text-[hsl(var(--activity-autonomy))] border-[hsl(var(--activity-autonomy)/0.3)]',
  },
  feedback: {
    icon: Sparkles,
    label: 'Feedback',
    borderColor: 'border-l-[hsl(var(--status-info))]',
    badgeColor: 'bg-[hsl(var(--status-info)/0.15)] text-[hsl(var(--status-info))] border-[hsl(var(--status-info)/0.3)]',
  },
  permission_change: {
    icon: Settings,
    label: 'Permission',
    borderColor: 'border-l-[hsl(var(--status-warn))]',
    badgeColor: 'bg-[hsl(var(--status-warn)/0.15)] text-[hsl(var(--status-warn))] border-[hsl(var(--status-warn)/0.3)]',
  },
  system: {
    icon: Settings,
    label: 'System',
    borderColor: 'border-l-[hsl(var(--muted-foreground))]',
    badgeColor: 'bg-muted/50 text-muted-foreground border-border/60',
  },
};

export default function ActivityItem({ activity }) {
  const [expanded, setExpanded] = useState(false);
  const config = typeConfig[activity.type] || typeConfig.system;
  const Icon = config.icon;

  const details = activity.details || {};
  const timestamp = activity.timestamp
    ? new Date(activity.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '';

  const getTitle = () => {
    if (activity.type === 'model_call') {
      return `${details.provider || 'unknown'} / ${details.model || 'unknown'}`;
    }
    if (activity.type === 'tool_execution') {
      return `${details.tool || 'terminal'}: ${details.command || ''}`;
    }
    if (activity.type === 'memory_write') {
      return `Learned: ${details.memory_type || 'fact'}`;
    }
    if (activity.type === 'autonomy') {
      return details.event || 'Task action';
    }
    if (activity.type === 'permission_change') {
      return 'Permission updated';
    }
    if (activity.type === 'system') {
      return details.event || 'System event';
    }
    return activity.type;
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.15 }}
      className={`border-l-[3px] ${config.borderColor} bg-card/50 rounded-r-lg p-3 transition-colors duration-200 hover:bg-card/80`}
      data-testid="activity-timeline-item"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2 min-w-0">
          <Icon className="w-4 h-4 mt-0.5 flex-shrink-0 text-muted-foreground" />
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="outline" className={`text-[10px] ${config.badgeColor}`}>{config.label}</Badge>
              <span className="text-sm font-medium truncate">{getTitle()}</span>
            </div>
            {details.input_preview && (
              <p className="text-xs text-muted-foreground mt-1 truncate">{details.input_preview}</p>
            )}
            {details.content_preview && (
              <p className="text-xs text-muted-foreground mt-1 truncate">{details.content_preview}</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {activity.duration_ms > 0 && (
            <span className="text-[10px] font-mono-ombra text-muted-foreground flex items-center gap-1">
              <Clock className="w-3 h-3" />{activity.duration_ms}ms
            </span>
          )}
          <span className="text-[10px] font-mono-ombra text-muted-foreground">{timestamp}</span>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-muted-foreground hover:text-foreground transition-colors"
            data-testid="activity-item-expand-button"
          >
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {expanded && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="mt-2 p-2 bg-background/60 rounded-md font-mono-ombra text-xs overflow-auto max-h-48"
        >
          <pre className="whitespace-pre-wrap">{JSON.stringify(details, null, 2)}</pre>
        </motion.div>
      )}
    </motion.div>
  );
}

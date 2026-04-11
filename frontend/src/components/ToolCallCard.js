import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { ChevronDown, ChevronUp, Clock, CheckCircle2, XCircle, Terminal } from 'lucide-react';
import ModelBadge from './ModelBadge';

export default function ToolCallCard({ toolCall }) {
  const [expanded, setExpanded] = useState(false);

  const statusIcon = toolCall.success ? (
    <CheckCircle2 className="w-4 h-4 text-[hsl(var(--status-ok))]" />
  ) : (
    <XCircle className="w-4 h-4 text-[hsl(var(--status-err))]" />
  );

  return (
    <Card
      className="bg-secondary/40 border-border/60 transition-colors duration-200 hover:border-border/80"
      data-testid="chat-tool-call-card"
    >
      <CardHeader className="py-2 px-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-[hsl(var(--activity-tool))]" />
            <CardTitle className="text-sm font-medium">{toolCall.tool || 'terminal'}</CardTitle>
            {statusIcon}
            {toolCall.duration_ms && (
              <Badge variant="outline" className="text-[10px] font-mono-ombra">
                <Clock className="w-3 h-3 mr-1" />
                {toolCall.duration_ms}ms
              </Badge>
            )}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpanded(!expanded)}
            data-testid="chat-tool-call-view-payload-button"
          >
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </Button>
        </div>
      </CardHeader>
      {expanded && (
        <CardContent className="py-2 px-3">
          <div className="bg-background/60 rounded-md p-2 font-mono-ombra text-xs space-y-1">
            {toolCall.command && <div><span className="text-muted-foreground">Command:</span> {toolCall.command}</div>}
            {toolCall.stdout && <div><span className="text-muted-foreground">Output:</span> <pre className="whitespace-pre-wrap mt-1">{toolCall.stdout}</pre></div>}
            {toolCall.stderr && <div className="text-[hsl(var(--status-err))]"><span className="text-muted-foreground">Error:</span> {toolCall.stderr}</div>}
            {toolCall.error && <div className="text-[hsl(var(--status-err))]">{toolCall.error}</div>}
          </div>
        </CardContent>
      )}
    </Card>
  );
}

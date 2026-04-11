import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Separator } from '../components/ui/separator';
import { Progress } from '../components/ui/progress';
import {
  Brain, Pin, PinOff, Trash2, Search, RefreshCcw,
  Loader2, Filter, ArrowDown, Database, Sparkles, Clock, Zap
} from 'lucide-react';
import { getMemories, deleteMemory, clearMemories, pinMemory, runMemoryDecay } from '../lib/api';
import { toast } from 'sonner';

const MEMORY_TYPES = ['all', 'preference', 'habit', 'identity', 'context', 'conversation_summary', 'creative_idea', 'fact', 'knowledge'];

export default function MemoryManagement() {
  const [memories, setMemories] = useState([]);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [decaying, setDecaying] = useState(false);

  const fetchMemories = async (type) => {
    setLoading(true);
    try {
      const data = await getMemories(type === 'all' ? null : type, 100);
      setMemories(data || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  useEffect(() => { fetchMemories(filter); }, [filter]);

  const handlePin = async (id, pinned) => {
    try {
      await pinMemory(id, !pinned);
      toast.success(pinned ? 'Memory unpinned' : 'Memory pinned');
      fetchMemories(filter);
    } catch (e) { toast.error('Failed'); }
  };

  const handleDelete = async (id) => {
    try {
      await deleteMemory(id);
      toast.success('Memory deleted');
      fetchMemories(filter);
    } catch (e) { toast.error('Failed'); }
  };

  const handleDecay = async () => {
    setDecaying(true);
    try {
      const result = await runMemoryDecay();
      toast.success(`Decay complete: ${result.decayed} decayed, ${result.removed} removed`);
      fetchMemories(filter);
    } catch (e) { toast.error('Decay failed'); }
    setDecaying(false);
  };

  const handleClearAll = async () => {
    if (window.confirm('Clear all memories? This cannot be undone.')) {
      await clearMemories();
      toast.success('All memories cleared');
      fetchMemories(filter);
    }
  };

  const filteredMemories = memories.filter(m =>
    !search || m.content?.toLowerCase().includes(search.toLowerCase())
  );

  const pinnedCount = memories.filter(m => m.pinned).length;
  const avgScore = memories.length > 0
    ? (memories.reduce((s, m) => s + (m.utility_score || 0), 0) / memories.length).toFixed(2)
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight" data-testid="memories-title">Memory Management</h1>
          <p className="text-sm text-muted-foreground mt-1">View, pin, search, and manage what Ombra remembers</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleDecay} disabled={decaying} data-testid="memory-decay-button">
            {decaying ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <ArrowDown className="w-4 h-4 mr-1" />}
            Run Decay
          </Button>
          <Button variant="ghost" size="sm" onClick={() => fetchMemories(filter)}>
            <RefreshCcw className="w-4 h-4 mr-1" /> Refresh
          </Button>
          <Button variant="ghost" size="sm" onClick={handleClearAll} className="text-destructive">
            <Trash2 className="w-4 h-4 mr-1" /> Clear All
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        <Card className="bg-card/80 border-border/60">
          <CardContent className="py-3 px-4 text-center">
            <div className="text-2xl font-semibold">{memories.length}</div>
            <div className="text-xs text-muted-foreground flex items-center justify-center gap-1"><Database className="w-3 h-3" /> Total</div>
          </CardContent>
        </Card>
        <Card className="bg-card/80 border-border/60">
          <CardContent className="py-3 px-4 text-center">
            <div className="text-2xl font-semibold">{pinnedCount}</div>
            <div className="text-xs text-muted-foreground flex items-center justify-center gap-1"><Pin className="w-3 h-3" /> Pinned</div>
          </CardContent>
        </Card>
        <Card className="bg-card/80 border-border/60">
          <CardContent className="py-3 px-4 text-center">
            <div className="text-2xl font-semibold font-mono-ombra">{avgScore}</div>
            <div className="text-xs text-muted-foreground flex items-center justify-center gap-1"><Zap className="w-3 h-3" /> Avg Score</div>
          </CardContent>
        </Card>
        <Card className="bg-card/80 border-border/60">
          <CardContent className="py-3 px-4 text-center">
            <div className="text-2xl font-semibold">{memories.filter(m => m.type === 'creative_idea').length}</div>
            <div className="text-xs text-muted-foreground flex items-center justify-center gap-1"><Sparkles className="w-3 h-3" /> Ideas</div>
          </CardContent>
        </Card>
      </div>

      {/* Search + Filters */}
      <div className="flex gap-3 items-center flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search memories..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-9"
            data-testid="memory-search-input"
          />
        </div>
        <div className="flex gap-1 flex-wrap">
          {MEMORY_TYPES.map(t => (
            <Button
              key={t}
              variant={filter === t ? 'default' : 'outline'}
              size="sm"
              onClick={() => setFilter(t)}
              className="text-xs h-8 capitalize"
            >
              {t.replace('_', ' ')}
            </Button>
          ))}
        </div>
      </div>

      {/* Memory List */}
      <div className="space-y-2" data-testid="memory-list">
        {loading ? (
          <div className="flex items-center justify-center py-12"><Loader2 className="w-6 h-6 animate-spin" /></div>
        ) : filteredMemories.length === 0 ? (
          <Card className="bg-card/40 border-border/40">
            <CardContent className="py-10 text-center">
              <Brain className="w-10 h-10 mx-auto mb-3 text-muted-foreground/30" />
              <p className="text-sm text-muted-foreground">No memories found. Chat with Ombra to start building memory.</p>
            </CardContent>
          </Card>
        ) : (
          filteredMemories.map((mem, i) => (
            <motion.div
              key={mem._id || i}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.02 }}
            >
              <Card className={`bg-card/80 border-border/60 transition-all hover:border-border/80 ${
                mem.pinned ? 'ring-1 ring-primary/20' : ''
              }`}>
                <CardContent className="py-3 px-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline" className="text-[10px] capitalize">{mem.type?.replace('_', ' ')}</Badge>
                        {mem.pinned && (
                          <Badge variant="outline" className="text-[10px] text-primary border-primary/30">
                            <Pin className="w-3 h-3 mr-0.5" /> Pinned
                          </Badge>
                        )}
                        <Badge variant="outline" className="text-[10px] font-mono-ombra">
                          Score: {((mem.utility_score || 0) * 100).toFixed(0)}%
                        </Badge>
                        {mem.access_count > 0 && (
                          <Badge variant="outline" className="text-[10px] font-mono-ombra">
                            Accessed: {mem.access_count}x
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm">{mem.content}</p>
                      <div className="flex items-center gap-3 mt-1">
                        <span className="text-[10px] text-muted-foreground font-mono-ombra">
                          Source: {mem.source || 'unknown'}
                        </span>
                        {mem.created_at && (
                          <span className="text-[10px] text-muted-foreground font-mono-ombra flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(mem.created_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                      {/* Score bar */}
                      <div className="mt-2 flex items-center gap-2">
                        <div className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              (mem.utility_score || 0) > 0.7 ? 'bg-[hsl(var(--status-ok))]'
                              : (mem.utility_score || 0) > 0.4 ? 'bg-[hsl(var(--status-warn))]'
                              : 'bg-[hsl(var(--status-err))]'
                            }`}
                            style={{ width: `${(mem.utility_score || 0) * 100}%` }}
                          />
                        </div>
                        <span className="text-[10px] font-mono-ombra text-muted-foreground w-8">
                          {((mem.utility_score || 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                    <div className="flex flex-col gap-1">
                      <Button
                        variant="ghost" size="sm"
                        onClick={() => handlePin(mem._id, mem.pinned)}
                        className={mem.pinned ? 'text-primary' : 'text-muted-foreground'}
                        data-testid={`memory-pin-${mem._id}`}
                      >
                        {mem.pinned ? <PinOff className="w-4 h-4" /> : <Pin className="w-4 h-4" />}
                      </Button>
                      <Button
                        variant="ghost" size="sm"
                        onClick={() => handleDelete(mem._id)}
                        className="text-destructive"
                        data-testid={`memory-delete-${mem._id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))
        )}
      </div>
    </div>
  );
}

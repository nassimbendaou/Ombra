import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Separator } from '../components/ui/separator';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import {
  Bot, Plus, Code, Search, Map, Play, Trash2, Edit, Settings,
  Cpu, Cloud, Sparkles, Globe, Loader2, Send
} from 'lucide-react';
import { getAgents, createAgent, deleteAgent, runAgent } from '../lib/api';
import { toast } from 'sonner';

const iconMap = { code: Code, search: Search, map: Map, play: Play, bot: Bot, settings: Settings };

export default function Agents() {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [showRun, setShowRun] = useState(null);
  const [runInput, setRunInput] = useState('');
  const [runResult, setRunResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [form, setForm] = useState({
    name: '', description: '', system_prompt: '',
    tools_allowed: [], provider_preference: 'auto',
    temperature: 0.5, icon: 'bot', color: '#888888'
  });

  const fetchAgents = () => {
    getAgents().then(a => { setAgents(a); setLoading(false); }).catch(() => setLoading(false));
  };

  useEffect(() => { fetchAgents(); }, []);

  const handleCreate = async () => {
    try {
      await createAgent(form);
      toast.success('Agent created');
      setShowCreate(false);
      setForm({ name: '', description: '', system_prompt: '', tools_allowed: [], provider_preference: 'auto', temperature: 0.5, icon: 'bot', color: '#888888' });
      fetchAgents();
    } catch (e) { toast.error('Failed to create agent'); }
  };

  const handleDelete = async (agentId) => {
    try {
      await deleteAgent(agentId);
      toast.success('Agent deleted');
      fetchAgents();
    } catch (e) { toast.error(e.message || 'Cannot delete built-in agents'); }
  };

  const handleRun = async () => {
    if (!runInput.trim() || !showRun) return;
    setRunning(true);
    try {
      const result = await runAgent(showRun.agent_id, runInput);
      setRunResult(result);
    } catch (e) { toast.error('Agent run failed'); }
    setRunning(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight" data-testid="agents-title">Agents</h1>
          <p className="text-sm text-muted-foreground mt-1">Built-in specialists and custom agents for task delegation</p>
        </div>
        <Button onClick={() => setShowCreate(true)} data-testid="create-agent-button">
          <Plus className="w-4 h-4 mr-2" /> Create Agent
        </Button>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1,2,3,4].map(i => <div key={i} className="h-40 bg-card/40 rounded-xl animate-pulse" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {agents.map((agent) => {
            const Icon = iconMap[agent.icon] || Bot;
            return (
              <motion.div key={agent.agent_id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
                <Card className="bg-card/80 backdrop-blur border-border/60 hover:border-border/80 transition-all h-full">
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                          style={{ backgroundColor: `${agent.color}20`, color: agent.color }}>
                          <Icon className="w-5 h-5" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="text-sm font-semibold">{agent.name}</h3>
                            {agent.builtin && <Badge variant="outline" className="text-[10px]">Built-in</Badge>}
                            <Badge variant="outline" className="text-[10px] font-mono-ombra">{agent.role}</Badge>
                          </div>
                          <p className="text-xs text-muted-foreground mt-1">{agent.description}</p>
                          <div className="flex gap-1 mt-2 flex-wrap">
                            {agent.tools_allowed?.map(t => (
                              <Badge key={t} variant="outline" className="text-[9px]">{t}</Badge>
                            ))}
                            {agent.provider_preference && agent.provider_preference !== 'auto' && (
                              <Badge variant="outline" className="text-[9px] font-mono-ombra">{agent.provider_preference}</Badge>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="sm" onClick={() => { setShowRun(agent); setRunResult(null); setRunInput(''); }} data-testid={`run-agent-${agent.agent_id}`}>
                          <Play className="w-4 h-4" />
                        </Button>
                        {!agent.builtin && (
                          <Button variant="ghost" size="sm" onClick={() => handleDelete(agent.agent_id)} className="text-destructive">
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        )}
                      </div>
                    </div>
                    <div className="mt-3 p-2 bg-secondary/30 rounded-md">
                      <p className="text-[11px] text-muted-foreground font-mono-ombra line-clamp-2">{agent.system_prompt}</p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Create Agent Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-md" data-testid="create-agent-dialog">
          <DialogHeader>
            <DialogTitle>Create Custom Agent</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <Input placeholder="Agent name" value={form.name} onChange={e => setForm({...form, name: e.target.value})} data-testid="agent-name-input" />
            <Input placeholder="Description" value={form.description} onChange={e => setForm({...form, description: e.target.value})} />
            <textarea
              placeholder="System prompt (defines agent behavior)"
              value={form.system_prompt}
              onChange={e => setForm({...form, system_prompt: e.target.value})}
              className="w-full h-24 px-3 py-2 rounded-md bg-secondary/60 border border-border text-sm resize-none"
              data-testid="agent-prompt-input"
            />
            <div className="grid grid-cols-2 gap-2">
              <select
                value={form.provider_preference}
                onChange={e => setForm({...form, provider_preference: e.target.value})}
                className="h-10 px-3 rounded-md bg-secondary/60 border border-border text-sm"
              >
                <option value="auto">Auto Provider</option>
                <option value="ollama">Ollama</option>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="gemini">Gemini</option>
              </select>
              <Input
                type="color" value={form.color}
                onChange={e => setForm({...form, color: e.target.value})}
                className="h-10"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button onClick={handleCreate} disabled={!form.name || !form.system_prompt} data-testid="agent-create-submit">Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Run Agent Dialog */}
      <Dialog open={!!showRun} onOpenChange={() => setShowRun(null)}>
        <DialogContent className="max-w-lg" data-testid="run-agent-dialog">
          <DialogHeader>
            <DialogTitle>Run: {showRun?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">{showRun?.description}</p>
            <div className="flex gap-2">
              <Input
                placeholder="Enter message for agent..."
                value={runInput}
                onChange={e => setRunInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleRun()}
                data-testid="agent-run-input"
              />
              <Button onClick={handleRun} disabled={running || !runInput.trim()} data-testid="agent-run-button">
                {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </Button>
            </div>
            {runResult && (
              <div className="p-3 bg-secondary/30 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant="outline" className="text-[10px] font-mono-ombra">{runResult.provider}</Badge>
                  <span className="text-[10px] text-muted-foreground">{runResult.duration_ms}ms</span>
                </div>
                <p className="text-sm whitespace-pre-wrap">{runResult.response}</p>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

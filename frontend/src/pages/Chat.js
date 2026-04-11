import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import {
  Send, Zap, Trash2, Plus, PanelRightOpen, PanelRightClose,
  Eye, EyeOff, Cpu, Cloud, Sparkles, Globe, Loader2,
  Terminal, ChevronDown, AlertCircle, ThumbsUp, ThumbsDown, Bot
} from 'lucide-react';
import MessageBubble from '../components/MessageBubble';
import ModelBadge from '../components/ModelBadge';
import ToolCallCard from '../components/ToolCallCard';
import { sendChat, getChatHistory, clearChatHistory, executeTerminal, getAgents, submitFeedback } from '../lib/api';
import { toast } from 'sonner';

const PROVIDERS = [
  { value: null, label: 'Auto', icon: Zap },
  { value: 'ollama', label: 'Ollama', icon: Cpu },
  { value: 'openai', label: 'OpenAI', icon: Sparkles },
  { value: 'anthropic', label: 'Anthropic', icon: Cloud },
  { value: 'gemini', label: 'Gemini', icon: Globe },
];

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [agentStatus, setAgentStatus] = useState('idle');
  const [showReasoning, setShowReasoning] = useState(false);
  const [showInspector, setShowInspector] = useState(true);
  const [forceProvider, setForceProvider] = useState(null);
  const [whiteCardMode, setWhiteCardMode] = useState(false);
  const [lastRouting, setLastRouting] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [showProviderMenu, setShowProviderMenu] = useState(false);
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [showAgentMenu, setShowAgentMenu] = useState(false);
  const [feedbackGiven, setFeedbackGiven] = useState({});
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Load sessions + agents on mount
  useEffect(() => {
    getChatHistory().then(s => {
      if (Array.isArray(s)) setSessions(s);
    }).catch(() => {});
    getAgents().then(a => setAgents(a || [])).catch(() => {});
  }, []);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadSession = useCallback(async (sid) => {
    try {
      const data = await getChatHistory(sid);
      if (data && data.turns) {
        setMessages(data.turns);
        setSessionId(sid);
      }
    } catch (e) {
      toast.error('Failed to load session');
    }
  }, []);

  const handleNewChat = () => {
    setMessages([]);
    setSessionId(null);
    setLastRouting(null);
    setAgentStatus('idle');
  };

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || loading) return;

    setInput('');
    const userMessage = { role: 'user', content: msg, timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, userMessage]);
    setLoading(true);
    setAgentStatus('thinking');

    try {
      const result = await sendChat(msg, sessionId, forceProvider, whiteCardMode, selectedAgent);
      
      if (!sessionId) {
        setSessionId(result.session_id);
      }

      const assistantMessage = {
        role: 'assistant',
        content: result.response,
        timestamp: new Date().toISOString(),
        provider: result.provider,
        model: result.model,
        routing: result.routing,
        fallback_chain: result.fallback_chain,
        duration_ms: result.duration_ms,
        agent_id: result.agent_id,
        k1_prompt: result.k1_prompt,
        category: result.category
      };

      setMessages(prev => [...prev, assistantMessage]);
      setLastRouting(result.routing);
      setAgentStatus('done');

      // Refresh sessions
      getChatHistory().then(s => {
        if (Array.isArray(s)) setSessions(s);
      }).catch(() => {});

      setTimeout(() => setAgentStatus('idle'), 2000);
    } catch (error) {
      setAgentStatus('error');
      toast.error('Failed to get response: ' + error.message);
      setTimeout(() => setAgentStatus('idle'), 3000);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClearHistory = async () => {
    if (sessionId) {
      await clearChatHistory(sessionId);
      handleNewChat();
      toast.success('Chat history cleared');
    }
  };

  const statusConfig = {
    idle: { label: 'Ready', color: 'bg-[hsl(var(--status-ok))]', glow: 'shadow-[0_0_12px_hsl(var(--status-ok)/0.25)]' },
    thinking: { label: 'Thinking...', color: 'bg-[hsl(var(--status-info))]', glow: 'shadow-[0_0_18px_hsl(var(--status-info)/0.35)]', pulse: true },
    executing: { label: 'Executing...', color: 'bg-[hsl(var(--activity-autonomy))]', glow: 'shadow-[0_0_18px_hsl(var(--activity-autonomy)/0.30)]', pulse: true },
    done: { label: 'Done', color: 'bg-[hsl(var(--status-ok))]', glow: 'shadow-[0_0_18px_hsl(var(--status-ok)/0.25)]' },
    error: { label: 'Error', color: 'bg-[hsl(var(--status-err))]', glow: 'shadow-[0_0_18px_hsl(var(--status-err)/0.25)]' },
  };

  const currentStatus = statusConfig[agentStatus];

  return (
    <div className="flex gap-4 h-[calc(100vh-120px)]">
      {/* Messages Panel */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Chat header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">Chat</h1>
            <div className="flex items-center gap-2">
              <div className={`w-2.5 h-2.5 rounded-full ${currentStatus.color} ${currentStatus.glow} ${currentStatus.pulse ? 'animate-ombra-pulse' : ''}`} />
              <span className="text-xs text-muted-foreground font-mono-ombra">{currentStatus.label}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={handleNewChat} data-testid="chat-new-button">
              <Plus className="w-4 h-4 mr-1" /> New
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setShowReasoning(!showReasoning)} data-testid="chat-reasoning-toggle">
              {showReasoning ? <EyeOff className="w-4 h-4 mr-1" /> : <Eye className="w-4 h-4 mr-1" />}
              {showReasoning ? 'Hide' : 'Show'} Reasoning
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowInspector(!showInspector)}
              className="hidden lg:flex"
            >
              {showInspector ? <PanelRightClose className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
            </Button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-auto rounded-xl bg-card/30 border border-border/40 p-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4 animate-ombra-glow">
                <Zap className="w-8 h-8 text-primary" />
              </div>
              <h2 className="text-lg font-semibold">Hello! I'm Ombra</h2>
              <p className="text-sm text-muted-foreground mt-2 max-w-md">
                Your autonomous AI assistant. I can help with coding, analysis, planning, and more.
                I route between local (Ollama) and cloud models automatically.
              </p>
              <div className="flex gap-2 mt-4 flex-wrap justify-center">
                {['Explain your architecture', 'Run a terminal command', 'Help me plan a project'].map(s => (
                  <Button key={s} variant="outline" size="sm" className="text-xs" onClick={() => { setInput(s); }}>
                    {s}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i}>
              <MessageBubble message={msg} showReasoning={showReasoning} />
              {msg.role === 'assistant' && (
                <div className={`flex items-center gap-1 mt-1 ${i > 0 ? 'ml-11' : 'ml-11'}`}>
                  <Button
                    variant="ghost" size="sm"
                    className={`h-6 w-6 p-0 ${feedbackGiven[i] === 'positive' ? 'text-[hsl(var(--status-ok))]' : 'text-muted-foreground/50 hover:text-[hsl(var(--status-ok))]'}`}
                    onClick={() => {
                      if (sessionId) {
                        submitFeedback(sessionId, i, 'positive', '').catch(() => {});
                        setFeedbackGiven(prev => ({ ...prev, [i]: 'positive' }));
                        toast.success('Thanks for the feedback!');
                      }
                    }}
                    data-testid={`feedback-positive-${i}`}
                  >
                    <ThumbsUp className="w-3 h-3" />
                  </Button>
                  <Button
                    variant="ghost" size="sm"
                    className={`h-6 w-6 p-0 ${feedbackGiven[i] === 'negative' ? 'text-[hsl(var(--status-err))]' : 'text-muted-foreground/50 hover:text-[hsl(var(--status-err))]'}`}
                    onClick={() => {
                      if (sessionId) {
                        submitFeedback(sessionId, i, 'negative', '').catch(() => {});
                        setFeedbackGiven(prev => ({ ...prev, [i]: 'negative' }));
                        toast.info('Feedback recorded, I\'ll improve!');
                      }
                    }}
                    data-testid={`feedback-negative-${i}`}
                  >
                    <ThumbsDown className="w-3 h-3" />
                  </Button>
                  {msg.agent_id && msg.agent_id !== 'auto' && (
                    <Badge variant="outline" className="text-[9px] font-mono-ombra ml-1">{msg.agent_id}</Badge>
                  )}
                </div>
              )}
            </div>
          ))}

          {loading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-2 px-4 py-2"
            >
              <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
                <Loader2 className="w-4 h-4 text-primary animate-spin" />
              </div>
              <div className="flex gap-1">
                <div className="w-2 h-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </motion.div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Composer */}
        <div className="mt-3 bg-card/80 backdrop-blur border border-border/60 rounded-xl p-3">
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a message... (Shift+Enter for new line)"
                className="w-full bg-transparent resize-none text-sm outline-none min-h-[40px] max-h-[120px] py-2 px-1"
                rows={1}
                data-testid="chat-composer-textarea"
              />
            </div>
            <div className="flex items-end gap-2">
              {/* Provider selector */}
              <div className="relative">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowProviderMenu(!showProviderMenu)}
                  className="text-xs font-mono-ombra h-9"
                  data-testid="chat-composer-model-select"
                >
                  {PROVIDERS.find(p => p.value === forceProvider)?.label || 'Auto'}
                  <ChevronDown className="w-3 h-3 ml-1" />
                </Button>
                {showProviderMenu && (
                  <div className="absolute bottom-full mb-1 right-0 bg-popover border border-border rounded-lg shadow-lg p-1 z-50 min-w-[140px]">
                    {PROVIDERS.map(p => (
                      <button
                        key={p.label}
                        onClick={() => { setForceProvider(p.value); setShowProviderMenu(false); }}
                        className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-md text-sm hover:bg-secondary/50 transition-colors ${
                          forceProvider === p.value ? 'bg-secondary/70' : ''
                        }`}
                      >
                        <p.icon className="w-4 h-4" />
                        {p.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Agent selector */}
              <div className="relative">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowAgentMenu(!showAgentMenu)}
                  className="text-xs font-mono-ombra h-9"
                  data-testid="chat-agent-select"
                >
                  <Bot className="w-3 h-3 mr-1" />
                  {selectedAgent ? agents.find(a => a.agent_id === selectedAgent)?.name || 'Agent' : 'Auto'}
                  <ChevronDown className="w-3 h-3 ml-1" />
                </Button>
                {showAgentMenu && (
                  <div className="absolute bottom-full mb-1 right-0 bg-popover border border-border rounded-lg shadow-lg p-1 z-50 min-w-[160px]">
                    <button
                      onClick={() => { setSelectedAgent(null); setShowAgentMenu(false); }}
                      className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-md text-sm hover:bg-secondary/50 transition-colors ${!selectedAgent ? 'bg-secondary/70' : ''}`}
                    >
                      <Zap className="w-4 h-4" /> Auto
                    </button>
                    {agents.map(a => (
                      <button
                        key={a.agent_id}
                        onClick={() => { setSelectedAgent(a.agent_id); setShowAgentMenu(false); }}
                        className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-md text-sm hover:bg-secondary/50 transition-colors ${selectedAgent === a.agent_id ? 'bg-secondary/70' : ''}`}
                      >
                        <div className="w-4 h-4 rounded" style={{ backgroundColor: a.color || '#888' }} />
                        {a.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* White card mode */}
              <Button
                variant={whiteCardMode ? 'default' : 'outline'}
                size="sm"
                onClick={() => setWhiteCardMode(!whiteCardMode)}
                className="h-9"
                title="White Card Mode: Proactive suggestions"
              >
                <Sparkles className={`w-4 h-4 ${whiteCardMode ? 'text-primary-foreground' : ''}`} />
              </Button>

              {/* Send */}
              <Button
                onClick={handleSend}
                disabled={!input.trim() || loading}
                className="h-9"
                data-testid="chat-composer-send-button"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Inspector Panel */}
      <AnimatePresence>
        {showInspector && (
          <motion.div
            initial={{ opacity: 0, width: 0 }}
            animate={{ opacity: 1, width: 320 }}
            exit={{ opacity: 0, width: 0 }}
            className="hidden lg:flex flex-col overflow-hidden"
          >
            <Card className="h-full bg-card/80 backdrop-blur border-border/60 flex flex-col" data-testid="chat-inspector-tabs">
              <CardHeader className="py-3">
                <CardTitle className="text-sm">Inspector</CardTitle>
              </CardHeader>
              <CardContent className="flex-1 overflow-auto space-y-4">
                {/* Routing Info */}
                {lastRouting && (
                  <div className="space-y-2">
                    <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Routing Decision</h3>
                    <div className="p-2 bg-secondary/30 rounded-lg space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">Route</span>
                        <Badge variant="outline" className="text-[10px] font-mono-ombra">{lastRouting.route}</Badge>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">Score</span>
                        <span className="text-xs font-mono-ombra">{lastRouting.score}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">Provider</span>
                        <Badge variant="outline" className="text-[10px] font-mono-ombra">{lastRouting.suggested_provider}</Badge>
                      </div>
                      {lastRouting.reasons?.length > 0 && (
                        <div className="pt-1">
                          <span className="text-xs text-muted-foreground">Reasons:</span>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {lastRouting.reasons.map((r, i) => (
                              <Badge key={i} variant="outline" className="text-[9px] font-mono-ombra">{r}</Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Session Info */}
                <div className="space-y-2">
                  <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Session</h3>
                  <div className="p-2 bg-secondary/30 rounded-lg">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">ID</span>
                      <span className="text-[10px] font-mono-ombra truncate max-w-[180px]">{sessionId || 'New session'}</span>
                    </div>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-xs text-muted-foreground">Messages</span>
                      <span className="text-xs font-mono-ombra">{messages.length}</span>
                    </div>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-xs text-muted-foreground">White Card</span>
                      <span className="text-xs font-mono-ombra">{whiteCardMode ? 'On' : 'Off'}</span>
                    </div>
                  </div>
                </div>

                {/* Previous Sessions */}
                {sessions.length > 0 && (
                  <div className="space-y-2">
                    <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Previous Sessions</h3>
                    <div className="space-y-1">
                      {sessions.slice(0, 8).map(s => (
                        <button
                          key={s.session_id}
                          onClick={() => loadSession(s.session_id)}
                          className={`w-full text-left p-2 rounded-lg text-xs hover:bg-secondary/50 transition-colors ${
                            sessionId === s.session_id ? 'bg-secondary/70' : 'bg-secondary/20'
                          }`}
                        >
                          <div className="truncate">{s.preview || 'Empty session'}</div>
                          <div className="text-[10px] text-muted-foreground font-mono-ombra mt-0.5">
                            {s.updated_at ? new Date(s.updated_at).toLocaleDateString() : ''}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <Separator />
                <Button variant="ghost" size="sm" onClick={handleClearHistory} className="w-full text-xs text-destructive hover:text-destructive">
                  <Trash2 className="w-3 h-3 mr-1" /> Clear This Chat
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

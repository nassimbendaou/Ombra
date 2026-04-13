import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import {
  Send, Zap, Trash2, Plus, PanelRightOpen, PanelRightClose,
  Eye, EyeOff, Cpu, Cloud, Sparkles, Globe, Loader2,
  Terminal, ChevronDown, AlertCircle, ThumbsUp, ThumbsDown, Bot,
  ScrollText, ExternalLink, Folder, File, RefreshCw, ArrowLeft
} from 'lucide-react';
import MessageBubble from '../components/MessageBubble';
import ModelBadge from '../components/ModelBadge';
import ToolCallCard from '../components/ToolCallCard';
import { sendChat, streamChat, connectWebSocket, getChatHistory, clearChatHistory, executeTerminal, getAgents, submitFeedback, getActivity, getPreviewUrl, getPreviewDir } from '../lib/api';
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
  const [streamingText, setStreamingText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [remoteTyping, setRemoteTyping] = useState(false);
  const [enableTools, setEnableTools] = useState(true);
  const [streamingToolCalls, setStreamingToolCalls] = useState([]);
  const [inspectorTab, setInspectorTab] = useState('info');
  const [activityLogs, setActivityLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [previewPath, setPreviewPath] = useState('/tmp');
  const [previewEntries, setPreviewEntries] = useState([]);
  const [previewFile, setPreviewFile] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const wsRef = useRef(null);
  const streamAbortRef = useRef(null);

  // Load sessions + agents on mount
  useEffect(() => {
    getChatHistory().then(s => {
      if (Array.isArray(s)) setSessions(s);
    }).catch(() => {});
    getAgents().then(a => setAgents(a || [])).catch(() => {});

    // Connect WebSocket for live typing/presence events
    const ws = connectWebSocket((data) => {
      if (data.type === 'typing') setRemoteTyping(data.typing === true);
    });
    wsRef.current = ws;
    return () => { ws.close(); };
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

  const handleSend = () => {
    const msg = input.trim();
    if (!msg || loading || isStreaming) return;

    setInput('');
    const userMessage = { role: 'user', content: msg, timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, userMessage]);
    setLoading(true);
    setIsStreaming(true);
    setStreamingText('');
    setStreamingToolCalls([]);
    setAgentStatus('thinking');

    let accumulated = '';

    const ctrl = streamChat(
      msg, sessionId, forceProvider, whiteCardMode, selectedAgent,
      // onToken
      (token) => {
        accumulated += token;
        setStreamingText(accumulated);
        setLoading(false);
        setAgentStatus('executing');
      },
      // onDone
      (data) => {
        const finalText = accumulated || data.full_response || '';
        const assistantMessage = {
          role: 'assistant',
          content: finalText,
          timestamp: new Date().toISOString(),
          provider: data.provider,
          model: data.model,
          duration_ms: data.duration_ms,
          usage: data.usage,
          tool_calls: data.tool_calls || null,
        };
        setMessages(prev => [...prev, assistantMessage]);
        if (data.session_id && !sessionId) setSessionId(data.session_id);
        if (data.routing) setLastRouting(data.routing);
        setStreamingText('');
        setStreamingToolCalls([]);
        setIsStreaming(false);
        setLoading(false);
        setAgentStatus('done');
        getChatHistory().then(s => { if (Array.isArray(s)) setSessions(s); }).catch(() => {});
        setTimeout(() => setAgentStatus('idle'), 2000);
      },
      // onError
      (err) => {
        setStreamingText('');
        setStreamingToolCalls([]);
        setIsStreaming(false);
        setLoading(false);
        setAgentStatus('error');
        toast.error('Failed to get response: ' + err.message);
        setTimeout(() => setAgentStatus('idle'), 3000);
      },
      // enableTools
      enableTools || null,
      // onToolEvent
      (event) => {
        if (event.type === 'tool_start') {
          setStreamingToolCalls(prev => [...prev, { tool: event.tool, args: event.args, status: 'running' }]);
          setAgentStatus('executing');
        } else if (event.type === 'tool_result') {
          setStreamingToolCalls(prev => prev.map((tc, i) =>
            i === prev.length - 1 && tc.tool === event.tool
              ? { ...tc, status: event.success ? 'done' : 'error', output: event.output, success: event.success, preview_url: event.preview_url }
              : tc
          ));
          // Auto-open preview when a preview URL is detected
          if (event.preview_url) {
            setPreviewFile(null);
            setInspectorTab('preview');
            // Open in a small delay to let the UI update
            setTimeout(() => window.open(event.preview_url, 'ombra-preview'), 300);
          }
        }
      }
    );
    streamAbortRef.current = ctrl;
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

  // ── Logs loader ──
  const loadLogs = useCallback(async () => {
    setLogsLoading(true);
    try {
      const data = await getActivity('tool_execution', 30, 0);
      setActivityLogs(data.activities || []);
    } catch { setActivityLogs([]); }
    setLogsLoading(false);
  }, []);

  // ── Preview directory browser ──
  const loadPreviewDir = useCallback(async (dir) => {
    setPreviewLoading(true);
    setPreviewFile(null);
    try {
      const data = await getPreviewDir(dir);
      setPreviewPath(data.path);
      setPreviewEntries(data.entries || []);
    } catch (e) {
      toast.error('Cannot browse: ' + e.message);
      setPreviewEntries([]);
    }
    setPreviewLoading(false);
  }, []);

  // Auto-load when switching inspector tabs
  useEffect(() => {
    if (inspectorTab === 'logs') loadLogs();
    if (inspectorTab === 'preview' && previewEntries.length === 0) loadPreviewDir(previewPath);
  }, [inspectorTab]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-detect previewable files from tool calls
  useEffect(() => {
    const allToolCalls = messages
      .filter(m => m.tool_calls)
      .flatMap(m => m.tool_calls);
    // Check for preview_url in tool calls
    const lastPreview = [...allToolCalls].reverse().find(tc => tc.preview_url || tc.result?.preview_url);
    if (lastPreview) {
      const url = lastPreview.preview_url || lastPreview.result?.preview_url;
      if (url && url.includes('/api/preview?')) {
        // File preview via our API - extract path
        try {
          const path = new URL(url).searchParams.get('path');
          if (path) {
            setPreviewFile(path);
            setInspectorTab('preview');
          }
        } catch { /* external URL */ }
      }
      return;
    }
    // Fallback: check for write_file with HTML
    const lastWrite = [...allToolCalls].reverse().find(tc =>
      tc.tool === 'write_file' && tc.args?.path?.match(/\.(html|htm)$/i)
    );
    if (lastWrite?.args?.path) {
      setPreviewFile(lastWrite.args.path);
      setInspectorTab('preview');
    }
  }, [messages]);

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
              {msg.role === 'assistant' && msg.tool_calls && msg.tool_calls.length > 0 && (
                <div className="ml-11 mt-1.5 space-y-1.5">
                  {msg.tool_calls.map((tc, j) => (
                    <ToolCallCard key={j} toolCall={{
                      tool: tc.tool,
                      success: tc.success,
                      command: tc.args && tc.args.command ? tc.args.command : JSON.stringify(tc.args),
                      stdout: tc.result_preview || tc.result?.output,
                      stderr: !tc.success ? (tc.result?.output) : undefined,
                      preview_url: tc.preview_url || tc.result?.preview_url,
                    }} />
                  ))}
                </div>
              )}
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
                  {msg.usage && (
                    <span className="text-[9px] font-mono-ombra text-muted-foreground/40 ml-1">
                      {msg.usage.total_tokens}t{msg.usage.cost_usd > 0 ? ` · $${msg.usage.cost_usd.toFixed(4)}` : ''}
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}

          {/* Tool calls happening during streaming */}
          {isStreaming && streamingToolCalls.length > 0 && (
            <div className="ml-11 space-y-1.5">
              {streamingToolCalls.map((tc, i) => (
                <ToolCallCard key={i} toolCall={{
                  tool: tc.tool,
                  success: tc.success ?? (tc.status === 'done'),
                  command: tc.args && tc.args.command ? tc.args.command : JSON.stringify(tc.args),
                  stdout: tc.output,
                  stderr: tc.status === 'error' ? tc.output : undefined,
                  preview_url: tc.preview_url,
                }} />
              ))}
            </div>
          )}

          {/* Streaming bubble — shows tokens as they arrive */}
          {isStreaming && streamingText && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3">
              <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0 mt-1">
                <Loader2 className="w-4 h-4 text-primary animate-spin" />
              </div>
              <div className="bg-card border border-border/60 rounded-xl px-4 py-2.5 max-w-[85%]">
                <p className="text-sm whitespace-pre-wrap">{streamingText}<span className="inline-block w-0.5 h-4 bg-primary animate-pulse ml-0.5 align-text-bottom" /></p>
              </div>
            </motion.div>
          )}

          {/* Spinner while waiting for first token */}
          {loading && !streamingText && (
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

              {/* Agent tools mode */}
              <Button
                variant={enableTools ? 'default' : 'outline'}
                size="sm"
                onClick={() => setEnableTools(!enableTools)}
                className="h-9"
                title="Agent Mode: Ombra can run commands, search the web, write files, and more"
                data-testid="chat-agent-tools-toggle"
              >
                <Terminal className={`w-4 h-4 ${enableTools ? 'text-primary-foreground' : ''}`} />
              </Button>

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
                onClick={isStreaming ? () => { streamAbortRef.current?.abort(); setIsStreaming(false); setLoading(false); setStreamingText(''); } : handleSend}
                disabled={!isStreaming && (!input.trim() || loading)}
                className="h-9"
                data-testid="chat-composer-send-button"
              >
                {loading || isStreaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
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
            animate={{ opacity: 1, width: 360 }}
            exit={{ opacity: 0, width: 0 }}
            className="hidden lg:flex flex-col overflow-hidden"
          >
            <Card className="h-full bg-card/80 backdrop-blur border-border/60 flex flex-col" data-testid="chat-inspector-tabs">
              {/* Tab bar */}
              <div className="flex border-b border-border/40">
                {[
                  { id: 'info', label: 'Info', icon: Eye },
                  { id: 'logs', label: 'Logs', icon: ScrollText },
                  { id: 'preview', label: 'Preview', icon: Globe },
                ].map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => setInspectorTab(tab.id)}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors border-b-2 ${
                      inspectorTab === tab.id
                        ? 'border-primary text-primary'
                        : 'border-transparent text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <tab.icon className="w-3.5 h-3.5" />
                    {tab.label}
                  </button>
                ))}
              </div>

              <CardContent className="flex-1 overflow-auto p-3 space-y-4">

                {/* ═══ INFO TAB ═══ */}
                {inspectorTab === 'info' && (
                  <>
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
                    <div className="space-y-2">
                      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Session</h3>
                      <div className="p-2 bg-secondary/30 rounded-lg">
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-muted-foreground">ID</span>
                          <span className="text-[10px] font-mono-ombra truncate max-w-[200px]">{sessionId || 'New session'}</span>
                        </div>
                        <div className="flex items-center justify-between mt-1">
                          <span className="text-xs text-muted-foreground">Messages</span>
                          <span className="text-xs font-mono-ombra">{messages.length}</span>
                        </div>
                        <div className="flex items-center justify-between mt-1">
                          <span className="text-xs text-muted-foreground">Tools</span>
                          <span className="text-xs font-mono-ombra">{enableTools ? 'On' : 'Off'}</span>
                        </div>
                      </div>
                    </div>
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
                    <Separator />
                    <Button variant="ghost" size="sm" onClick={handleClearHistory} className="w-full text-xs text-destructive hover:text-destructive">
                      <Trash2 className="w-3 h-3 mr-1" /> Clear This Chat
                    </Button>
                  </>
                )}

                {/* ═══ LOGS TAB ═══ */}
                {inspectorTab === 'logs' && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Tool Executions</h3>
                      <Button variant="ghost" size="sm" onClick={loadLogs} className="h-6 w-6 p-0">
                        <RefreshCw className={`w-3 h-3 ${logsLoading ? 'animate-spin' : ''}`} />
                      </Button>
                    </div>
                    {activityLogs.length === 0 && !logsLoading && (
                      <p className="text-xs text-muted-foreground text-center py-4">No tool executions yet</p>
                    )}
                    {activityLogs.map((log, i) => {
                      const d = log.details || {};
                      const ts = log.timestamp ? new Date(log.timestamp) : null;
                      return (
                        <div key={log._id || i} className="p-2 bg-secondary/30 rounded-lg space-y-1">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-1.5">
                              <Terminal className="w-3 h-3 text-[hsl(var(--activity-tool))]" />
                              <span className="text-xs font-medium">{d.tool || log.type || '?'}</span>
                            </div>
                            <span className="text-[9px] font-mono-ombra text-muted-foreground">
                              {ts ? ts.toLocaleTimeString() : ''}
                            </span>
                          </div>
                          {d.command && (
                            <div className="text-[10px] font-mono-ombra bg-background/50 rounded px-1.5 py-1 truncate" title={d.command}>
                              $ {d.command}
                            </div>
                          )}
                          {d.action && !d.command && (
                            <div className="text-[10px] font-mono-ombra text-muted-foreground">
                              {d.action}{d.path ? `: ${d.path}` : ''}
                            </div>
                          )}
                          {d.output_preview && (
                            <div className="text-[10px] font-mono-ombra text-muted-foreground/70 truncate" title={d.output_preview}>
                              {d.output_preview}
                            </div>
                          )}
                          <div className="flex items-center gap-2">
                            {d.success !== undefined && (
                              <Badge variant={d.success ? 'outline' : 'destructive'} className="text-[9px]">
                                {d.success ? 'OK' : 'ERR'}
                              </Badge>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* ═══ PREVIEW TAB ═══ */}
                {inspectorTab === 'preview' && (
                  <div className="space-y-2 h-full flex flex-col">
                    {/* If a specific file is selected for preview */}
                    {previewFile ? (
                      <div className="flex-1 flex flex-col">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-1.5 min-w-0">
                            <File className="w-3 h-3 flex-shrink-0 text-primary" />
                            <span className="text-[10px] font-mono-ombra truncate">{previewFile}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={() => window.open(getPreviewUrl(previewFile), '_blank')}>
                              <ExternalLink className="w-3 h-3" />
                            </Button>
                            <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={() => setPreviewFile(null)}>
                              <ArrowLeft className="w-3 h-3" />
                            </Button>
                          </div>
                        </div>
                        <div className="flex-1 rounded-lg overflow-hidden border border-border/40 bg-white min-h-[300px]">
                          <iframe
                            src={getPreviewUrl(previewFile)}
                            title="Preview"
                            className="w-full h-full min-h-[300px]"
                            sandbox="allow-scripts allow-same-origin"
                            style={{ border: 'none' }}
                          />
                        </div>
                      </div>
                    ) : (
                      /* File browser */
                      <>
                        <div className="flex items-center justify-between">
                          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Browse Files</h3>
                          <Button variant="ghost" size="sm" onClick={() => loadPreviewDir(previewPath)} className="h-6 w-6 p-0">
                            <RefreshCw className={`w-3 h-3 ${previewLoading ? 'animate-spin' : ''}`} />
                          </Button>
                        </div>
                        <div className="text-[10px] font-mono-ombra text-muted-foreground bg-secondary/30 rounded px-2 py-1 truncate">
                          {previewPath}
                        </div>
                        {/* Go up button */}
                        {previewPath !== '/' && (
                          <button
                            onClick={() => {
                              const parent = previewPath.split('/').slice(0, -1).join('/') || '/';
                              loadPreviewDir(parent);
                            }}
                            className="w-full text-left p-1.5 rounded text-xs hover:bg-secondary/50 transition-colors flex items-center gap-1.5"
                          >
                            <ArrowLeft className="w-3 h-3 text-muted-foreground" />
                            <span className="text-muted-foreground">..</span>
                          </button>
                        )}
                        <div className="space-y-0.5 max-h-[400px] overflow-auto">
                          {previewEntries.map((entry, i) => (
                            <button
                              key={i}
                              onClick={() => {
                                const full = `${previewPath}/${entry.name}`;
                                if (entry.is_dir) {
                                  loadPreviewDir(full);
                                } else if (['.html', '.htm', '.svg', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.txt', '.json', '.md', '.css', '.js'].includes(entry.ext)) {
                                  setPreviewFile(full);
                                }
                              }}
                              className="w-full text-left p-1.5 rounded text-xs hover:bg-secondary/50 transition-colors flex items-center gap-1.5"
                            >
                              {entry.is_dir ? (
                                <Folder className="w-3 h-3 text-[hsl(var(--activity-autonomy))]" />
                              ) : (
                                <File className="w-3 h-3 text-muted-foreground" />
                              )}
                              <span className="truncate flex-1">{entry.name}</span>
                              {entry.size != null && (
                                <span className="text-[9px] font-mono-ombra text-muted-foreground">
                                  {entry.size > 1024 ? `${(entry.size / 1024).toFixed(1)}K` : `${entry.size}B`}
                                </span>
                              )}
                            </button>
                          ))}
                          {previewEntries.length === 0 && !previewLoading && (
                            <p className="text-xs text-muted-foreground text-center py-4">Empty directory</p>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

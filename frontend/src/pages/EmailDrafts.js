import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import {
  Mail, Send, Trash2, RefreshCcw, Loader2, CheckCircle2, Inbox, AlertCircle
} from 'lucide-react';
import { getEmailDrafts, sendEmailDraft, deleteEmailDraft } from '../lib/api';
import { toast } from 'sonner';

export default function EmailDrafts() {
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState({});

  const loadDrafts = useCallback(async () => {
    try {
      const res = await getEmailDrafts();
      setDrafts(res.drafts || []);
    } catch {
      toast.error('Failed to load drafts');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadDrafts(); }, [loadDrafts]);

  const handleSend = async (id) => {
    setActionLoading(prev => ({ ...prev, [id]: 'sending' }));
    try {
      const res = await sendEmailDraft(id);
      if (res.success) {
        toast.success(res.message || 'Email sent!');
        setDrafts(prev => prev.filter(d => d._id !== id));
      } else {
        toast.error(res.error || 'Send failed');
      }
    } catch {
      toast.error('Could not reach server');
    } finally {
      setActionLoading(prev => ({ ...prev, [id]: null }));
    }
  };

  const handleDiscard = async (id) => {
    setActionLoading(prev => ({ ...prev, [id]: 'deleting' }));
    try {
      await deleteEmailDraft(id);
      toast.success('Draft discarded');
      setDrafts(prev => prev.filter(d => d._id !== id));
    } catch {
      toast.error('Failed to discard');
    } finally {
      setActionLoading(prev => ({ ...prev, [id]: null }));
    }
  };

  const formatDate = (iso) => {
    try {
      const d = new Date(iso);
      const now = new Date();
      const diffMs = now - d;
      if (diffMs < 60000) return 'just now';
      if (diffMs < 3600000) return `${Math.floor(diffMs / 60000)}m ago`;
      if (diffMs < 86400000) return `${Math.floor(diffMs / 3600000)}h ago`;
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch { return ''; }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
      className="max-w-4xl mx-auto space-y-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Mail className="w-5 h-5 text-primary" />
            </div>
            Email Drafts
          </h1>
          <p className="text-muted-foreground mt-1">
            Review and approve emails Ombra has prepared for you
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => { setLoading(true); loadDrafts(); }}>
          <RefreshCcw className="w-4 h-4 mr-2" /> Refresh
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      ) : drafts.length === 0 ? (
        <Card className="bg-card/80 backdrop-blur border-border/60">
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-16 h-16 rounded-2xl bg-muted/30 flex items-center justify-center mb-4">
              <Inbox className="w-8 h-8 text-muted-foreground/50" />
            </div>
            <h3 className="text-lg font-medium text-muted-foreground">No pending drafts</h3>
            <p className="text-sm text-muted-foreground/70 mt-1">
              When Ombra prepares an email, it will appear here for your review
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {drafts.length} draft{drafts.length !== 1 ? 's' : ''} pending review
          </p>
          <AnimatePresence>
            {drafts.map(draft => (
              <motion.div
                key={draft._id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: -100, height: 0 }}
                transition={{ duration: 0.2 }}
              >
                <Card className="bg-card/80 backdrop-blur border-border/60 hover:border-border/80 transition-colors">
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <CardTitle className="text-base font-semibold truncate">
                          {draft.subject || '(no subject)'}
                        </CardTitle>
                        <CardDescription className="flex items-center gap-2 mt-1">
                          <span>To: <span className="text-foreground/80">{draft.to}</span></span>
                          <span className="text-muted-foreground/40">•</span>
                          <span>{formatDate(draft.created_at)}</span>
                        </CardDescription>
                      </div>
                      {draft.html && (
                        <Badge variant="outline" className="text-[10px] shrink-0">HTML</Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="bg-secondary/30 rounded-lg p-3 max-h-48 overflow-y-auto">
                      {draft.html ? (
                        <div className="text-sm prose prose-invert max-w-none" dangerouslySetInnerHTML={{ __html: draft.body }} />
                      ) : (
                        <pre className="text-sm whitespace-pre-wrap font-sans text-foreground/85">{draft.body}</pre>
                      )}
                    </div>
                    <Separator />
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        onClick={() => handleSend(draft._id)}
                        disabled={!!actionLoading[draft._id]}
                      >
                        {actionLoading[draft._id] === 'sending'
                          ? <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          : <Send className="w-4 h-4 mr-2" />}
                        Approve & Send
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => handleDiscard(draft._id)}
                        disabled={!!actionLoading[draft._id]}
                      >
                        {actionLoading[draft._id] === 'deleting'
                          ? <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          : <Trash2 className="w-4 h-4 mr-2" />}
                        Discard
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </motion.div>
  );
}

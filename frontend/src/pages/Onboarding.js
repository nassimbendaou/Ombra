import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import { Zap, Terminal, FolderOpen, Send, ArrowRight, Shield, Sparkles } from 'lucide-react';
import { completeOnboarding } from '../lib/api';
import { toast } from 'sonner';

export default function Onboarding() {
  const [step, setStep] = useState(0);
  const [perms, setPerms] = useState({ terminal: false, filesystem: false, telegram: false });
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleComplete = async () => {
    setLoading(true);
    try {
      await completeOnboarding(perms);
      toast.success('Welcome to Ombra!');
      navigate('/');
    } catch (e) {
      toast.error('Failed to complete setup');
    }
    setLoading(false);
  };

  return (
    <div className="dark min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {step === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center space-y-6"
          >
            <div className="w-20 h-20 mx-auto rounded-2xl bg-primary/10 flex items-center justify-center animate-ombra-glow">
              <Zap className="w-10 h-10 text-primary" />
            </div>
            <div>
              <h1 className="text-4xl font-semibold tracking-tight">Ombra</h1>
              <p className="text-lg text-muted-foreground mt-2">Your Autonomous AI Assistant</p>
            </div>
            <p className="text-sm text-muted-foreground max-w-md mx-auto">
              I'm an intelligent agent that runs locally with Ollama and falls back to cloud AI for complex tasks.
              I learn from our interactions, can execute tools, and proactively suggest improvements.
            </p>
            <div className="flex flex-wrap gap-2 justify-center">
              <Badge variant="outline">Smart Routing</Badge>
              <Badge variant="outline">Local + Cloud AI</Badge>
              <Badge variant="outline">Memory System</Badge>
              <Badge variant="outline">Tool Execution</Badge>
              <Badge variant="outline">Autonomous Tasks</Badge>
            </div>
            <Button onClick={() => setStep(1)} size="lg" className="mt-4">
              Get Started <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </motion.div>
        )}

        {step === 1 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card className="bg-card/80 backdrop-blur border-border/60">
              <CardHeader className="text-center">
                <div className="w-12 h-12 mx-auto rounded-xl bg-primary/10 flex items-center justify-center mb-4">
                  <Shield className="w-6 h-6 text-primary" />
                </div>
                <CardTitle>Set Permissions</CardTitle>
                <CardDescription>Choose what Ombra can access. You can change these anytime in Settings.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
                  <div className="flex items-center gap-3">
                    <Terminal className="w-5 h-5 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">Terminal Access</p>
                      <p className="text-xs text-muted-foreground">Run shell commands (sandboxed)</p>
                    </div>
                  </div>
                  <Switch
                    checked={perms.terminal}
                    onCheckedChange={v => setPerms({ ...perms, terminal: v })}
                    data-testid="onboarding-terminal-switch"
                  />
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
                  <div className="flex items-center gap-3">
                    <FolderOpen className="w-5 h-5 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">File System Access</p>
                      <p className="text-xs text-muted-foreground">Read and write files</p>
                    </div>
                  </div>
                  <Switch
                    checked={perms.filesystem}
                    onCheckedChange={v => setPerms({ ...perms, filesystem: v })}
                    data-testid="onboarding-filesystem-switch"
                  />
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
                  <div className="flex items-center gap-3">
                    <Send className="w-5 h-5 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">Telegram Integration</p>
                      <p className="text-xs text-muted-foreground">Send notifications (requires token)</p>
                    </div>
                  </div>
                  <Switch
                    checked={perms.telegram}
                    onCheckedChange={v => setPerms({ ...perms, telegram: v })}
                    data-testid="onboarding-telegram-switch"
                  />
                </div>

                <div className="flex gap-3 pt-4">
                  <Button variant="outline" onClick={() => setStep(0)} className="flex-1">
                    Back
                  </Button>
                  <Button onClick={handleComplete} disabled={loading} className="flex-1">
                    {loading ? 'Setting up...' : 'Launch Ombra'}
                    <Sparkles className="w-4 h-4 ml-2" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </div>
    </div>
  );
}

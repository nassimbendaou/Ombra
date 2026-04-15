import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Separator } from '../components/ui/separator';
import {
  Eye, Monitor, Loader2, Image, Upload, Camera, ScanSearch,
  Globe, MousePointer, ArrowRight, FlaskConical, Wand2
} from 'lucide-react';
import { analyzeImage } from '../lib/api';
import { toast } from 'sonner';

export default function ToolsLab() {
  const [tab, setTab] = useState('vision'); // vision | computer
  // Vision state
  const [imageUrl, setImageUrl] = useState('');
  const [visionMode, setVisionMode] = useState('describe');
  const [visionPrompt, setVisionPrompt] = useState('');
  const [visionResult, setVisionResult] = useState(null);
  const [visionLoading, setVisionLoading] = useState(false);

  const handleAnalyze = async () => {
    if (!imageUrl.trim()) { toast.error('Enter an image URL'); return; }
    setVisionLoading(true);
    setVisionResult(null);
    try {
      const data = await analyzeImage(imageUrl, visionMode, visionPrompt || undefined);
      setVisionResult(data);
      toast.success('Analysis complete');
    } catch (e) {
      toast.error('Vision analysis failed');
    }
    setVisionLoading(false);
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-rose-500/20 flex items-center justify-center">
            <FlaskConical className="w-5 h-5 text-rose-400" />
          </div>
          Tools Lab
        </h1>
        <p className="text-muted-foreground mt-1">
          Vision analysis, browser automation, and experimental tools
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-secondary/30 rounded-lg w-fit">
        <Button
          variant={tab === 'vision' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setTab('vision')}
          className={tab !== 'vision' ? 'text-muted-foreground' : ''}
        >
          <Eye className="w-4 h-4 mr-1.5" />
          Vision
        </Button>
        <Button
          variant={tab === 'computer' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setTab('computer')}
          className={tab !== 'computer' ? 'text-muted-foreground' : ''}
        >
          <Monitor className="w-4 h-4 mr-1.5" />
          Computer Use
        </Button>
      </div>

      {/* Vision Tab */}
      {tab === 'vision' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
          <Card className="bg-card/50 border-border/40">
            <CardContent className="p-4 space-y-4">
              {/* Image URL */}
              <div>
                <label className="text-xs text-muted-foreground mb-1.5 block">Image URL</label>
                <Input
                  placeholder="https://example.com/image.png"
                  value={imageUrl}
                  onChange={e => setImageUrl(e.target.value)}
                />
              </div>

              {/* Mode selector */}
              <div>
                <label className="text-xs text-muted-foreground mb-1.5 block">Analysis Mode</label>
                <div className="flex gap-2 flex-wrap">
                  {[
                    { id: 'describe', label: 'Describe', icon: Eye },
                    { id: 'ocr', label: 'OCR', icon: ScanSearch },
                    { id: 'ui_analysis', label: 'UI Analysis', icon: Monitor },
                    { id: 'custom', label: 'Custom', icon: Wand2 },
                  ].map(m => (
                    <Button
                      key={m.id}
                      variant={visionMode === m.id ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setVisionMode(m.id)}
                    >
                      <m.icon className="w-3.5 h-3.5 mr-1.5" />
                      {m.label}
                    </Button>
                  ))}
                </div>
              </div>

              {/* Custom prompt */}
              {visionMode === 'custom' && (
                <div>
                  <label className="text-xs text-muted-foreground mb-1.5 block">Custom Prompt</label>
                  <Input
                    placeholder="What should I analyze in this image?"
                    value={visionPrompt}
                    onChange={e => setVisionPrompt(e.target.value)}
                  />
                </div>
              )}

              <Button onClick={handleAnalyze} disabled={visionLoading} className="w-full">
                {visionLoading ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Eye className="w-4 h-4 mr-2" />
                )}
                Analyze Image
              </Button>
            </CardContent>
          </Card>

          {/* Preview + Result */}
          {(imageUrl || visionResult) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {imageUrl && (
                <Card className="bg-card/50 border-border/40 overflow-hidden">
                  <CardContent className="p-0">
                    <img
                      src={imageUrl}
                      alt="Preview"
                      className="w-full h-64 object-contain bg-black/30"
                      onError={e => { e.target.style.display = 'none'; }}
                    />
                  </CardContent>
                </Card>
              )}
              {visionResult && (
                <Card className="bg-card/50 border-border/40">
                  <CardHeader className="pb-2 pt-4 px-4">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Eye className="w-4 h-4 text-rose-400" />
                      Result
                      <Badge className="bg-rose-500/15 text-rose-400 border-0 text-[10px]">
                        {visionResult.model || 'vision'}
                      </Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-4">
                    <div className="text-sm whitespace-pre-wrap leading-relaxed">
                      {visionResult.description || visionResult.text || visionResult.analysis || JSON.stringify(visionResult, null, 2)}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </motion.div>
      )}

      {/* Computer Use Tab */}
      {tab === 'computer' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
          <Card className="bg-card/50 border-border/40">
            <CardContent className="p-6 text-center">
              <Monitor className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
              <h3 className="font-semibold mb-2">Browser Automation</h3>
              <p className="text-sm text-muted-foreground mb-4 max-w-md mx-auto">
                Control a headless browser via chat — navigate pages, take screenshots,
                fill forms, and extract content. Use natural language in the chat to interact.
              </p>
              <Separator className="my-4" />
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-left">
                {[
                  { icon: Globe, title: 'Navigate', desc: 'Open any URL and browse websites' },
                  { icon: Camera, title: 'Screenshot', desc: 'Capture full-page or element screenshots' },
                  { icon: MousePointer, title: 'Interact', desc: 'Click, type, scroll, and fill forms' },
                ].map((feat, i) => (
                  <div key={feat.title} className="flex items-start gap-2 bg-background/30 rounded-lg p-3">
                    <feat.icon className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
                    <div>
                      <h4 className="text-xs font-semibold">{feat.title}</h4>
                      <p className="text-[11px] text-muted-foreground">{feat.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
              <Separator className="my-4" />
              <p className="text-xs text-muted-foreground">
                Try in chat: <code className="bg-background/60 px-1.5 py-0.5 rounded">"Navigate to github.com and take a screenshot"</code>
              </p>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
}

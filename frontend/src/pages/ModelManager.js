import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Progress } from '../components/ui/progress';
import {
  Cpu, Download, Trash2, CheckCircle2, HardDrive, Zap,
  RefreshCcw, Loader2, AlertCircle, Brain
} from 'lucide-react';
import { getOllamaModels, getModelRecommendations, pullOllamaModel, deleteOllamaModel, getK1Prompts, getK1Distillations, getSettings, updateSettings } from '../lib/api';
import { toast } from 'sonner';

const RAM_TIERS = [
  { value: '4gb', label: '4 GB', description: 'Ultra-light models only' },
  { value: '8gb', label: '8 GB', description: '3B-7B models' },
  { value: '16gb', label: '16 GB', description: '7B-13B models' },
  { value: '32gb', label: '32 GB+', description: '13B+ models' },
];

export default function ModelManager() {
  const [installed, setInstalled] = useState([]);
  const [recommendations, setRecommendations] = useState(null);
  const [k1Prompts, setK1Prompts] = useState([]);
  const [distillations, setDistillations] = useState([]);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pulling, setPulling] = useState(null);
  const [tab, setTab] = useState('installed');

  const fetchData = async () => {
    setLoading(true);
    try {
      const [models, recs, prompts, dists, sett] = await Promise.all([
        getOllamaModels().catch(() => ({ models: [] })),
        getModelRecommendations().catch(() => null),
        getK1Prompts().catch(() => []),
        getK1Distillations().catch(() => []),
        getSettings().catch(() => null),
      ]);
      setInstalled(models.models || []);
      setRecommendations(recs);
      setK1Prompts(prompts);
      setDistillations(dists);
      setSettings(sett);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const handlePull = async (modelName) => {
    setPulling(modelName);
    toast.info(`Downloading ${modelName}... This may take a while.`);
    try {
      const result = await pullOllamaModel(modelName);
      if (result.success) {
        toast.success(`${modelName} downloaded successfully!`);
        fetchData();
      } else {
        toast.error(`Failed: ${result.error}`);
      }
    } catch (e) { toast.error('Download failed'); }
    setPulling(null);
  };

  const handleDelete = async (modelName) => {
    try {
      await deleteOllamaModel(modelName);
      toast.success(`${modelName} deleted`);
      fetchData();
    } catch (e) { toast.error('Delete failed'); }
  };

  const handleRamChange = async (tier) => {
    try {
      await updateSettings({ hardware_ram: tier });
      fetchData();
    } catch (e) { toast.error('Failed to update'); }
  };

  const formatSize = (bytes) => {
    if (!bytes) return 'N/A';
    const gb = bytes / (1024 * 1024 * 1024);
    if (gb >= 1) return `${gb.toFixed(1)} GB`;
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(0)} MB`;
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight" data-testid="models-title">Ombra-K1 Model Manager</h1>
        <p className="text-sm text-muted-foreground mt-1">Manage local models, view K1 learning insights, and optimize for your hardware</p>
      </div>

      {/* Tab buttons */}
      <div className="flex gap-2" data-testid="model-manager-tabs">
        {['installed', 'recommended', 'k1-insights'].map(t => (
          <Button key={t} variant={tab === t ? 'default' : 'outline'} size="sm" onClick={() => setTab(t)} className="capitalize">
            {t === 'k1-insights' ? 'K1 Insights' : t}
          </Button>
        ))}
      </div>

      {/* Hardware Config */}
      <Card className="bg-card/80 backdrop-blur border-border/60">
        <CardContent className="py-3 px-4">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <HardDrive className="w-4 h-4 text-primary" />
              <span className="text-sm font-medium">Your RAM:</span>
            </div>
            {RAM_TIERS.map(tier => (
              <Button
                key={tier.value}
                variant={(settings?.hardware_ram || '16gb') === tier.value ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleRamChange(tier.value)}
                className="text-xs"
                data-testid={`ram-tier-${tier.value}`}
              >
                {tier.label}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <div className="flex items-center justify-center py-12"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : (
        <>
          {/* Installed Models */}
          {tab === 'installed' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-medium">Installed Models ({installed.length})</h2>
                <Button variant="ghost" size="sm" onClick={fetchData}><RefreshCcw className="w-4 h-4 mr-1" /> Refresh</Button>
              </div>
              {installed.length === 0 ? (
                <Card className="bg-card/40 border-border/40">
                  <CardContent className="py-8 text-center">
                    <Cpu className="w-10 h-10 mx-auto mb-3 text-muted-foreground/30" />
                    <p className="text-sm text-muted-foreground">No models installed. Check recommendations to download one.</p>
                  </CardContent>
                </Card>
              ) : (
                installed.map((model, i) => (
                  <motion.div key={model.name} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                    <Card className="bg-card/80 border-border/60">
                      <CardContent className="py-3 px-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
                              <Cpu className="w-4 h-4 text-primary" />
                            </div>
                            <div>
                              <h3 className="text-sm font-semibold font-mono-ombra">{model.name}</h3>
                              <div className="flex items-center gap-2 mt-0.5">
                                <Badge variant="outline" className="text-[10px] font-mono-ombra">{formatSize(model.size)}</Badge>
                                {model.details?.parameter_size && <Badge variant="outline" className="text-[10px]">{model.details.parameter_size}</Badge>}
                                {model.details?.quantization_level && <Badge variant="outline" className="text-[10px]">{model.details.quantization_level}</Badge>}
                              </div>
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <Badge variant="outline" className="text-[10px] text-[hsl(var(--status-ok))] border-[hsl(var(--status-ok)/0.3)]">
                              <CheckCircle2 className="w-3 h-3 mr-1" /> Installed
                            </Badge>
                            <Button variant="ghost" size="sm" onClick={() => handleDelete(model.name)} className="text-destructive">
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
          )}

          {/* Recommended Models */}
          {tab === 'recommended' && recommendations && (
            <div className="space-y-3">
              <h2 className="text-lg font-medium">Recommended for {recommendations.ram_tier?.toUpperCase()} RAM</h2>
              {recommendations.recommendations?.map((rec, i) => (
                <motion.div key={rec.name} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                  <Card className="bg-card/80 border-border/60">
                    <CardContent className="py-3 px-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${rec.installed ? 'bg-[hsl(var(--status-ok)/0.15)]' : 'bg-secondary/60'}`}>
                            {rec.installed ? <CheckCircle2 className="w-4 h-4 text-[hsl(var(--status-ok))]" /> : <Download className="w-4 h-4 text-muted-foreground" />}
                          </div>
                          <div>
                            <h3 className="text-sm font-semibold font-mono-ombra">{rec.name}</h3>
                            <p className="text-xs text-muted-foreground">{rec.description}</p>
                            <div className="flex gap-1 mt-1">
                              <Badge variant="outline" className="text-[10px]">{rec.size}</Badge>
                              <Badge variant="outline" className="text-[10px]">{rec.params}</Badge>
                              <Badge variant="outline" className="text-[10px]">{rec.quantization}</Badge>
                            </div>
                          </div>
                        </div>
                        {rec.installed ? (
                          <Badge variant="outline" className="text-[10px] text-[hsl(var(--status-ok))]">Installed</Badge>
                        ) : (
                          <Button
                            size="sm"
                            onClick={() => handlePull(rec.name)}
                            disabled={!!pulling}
                            data-testid={`pull-model-${rec.name}`}
                          >
                            {pulling === rec.name ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4 mr-1" />}
                            {pulling === rec.name ? 'Pulling...' : 'Pull'}
                          </Button>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ))}
            </div>
          )}

          {/* K1 Insights */}
          {tab === 'k1-insights' && (
            <div className="space-y-4">
              {/* K1 Prompt Library */}
              <Card className="bg-card/80 border-border/60">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Brain className="w-5 h-5 text-primary" /> K1 Prompt Library
                  </CardTitle>
                  <CardDescription>Adaptive prompts that improve based on feedback</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {k1Prompts.map((p) => (
                      <div key={p.prompt_id} className="flex items-center justify-between p-2 rounded-lg bg-secondary/30">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-[10px]">{p.category}</Badge>
                          <span className="text-sm font-medium">{p.name}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="text-right">
                            <div className="text-xs font-mono-ombra">
                              Score: {(p.performance_score * 100).toFixed(0)}%
                            </div>
                            <div className="text-[10px] text-muted-foreground">
                              {p.usage_count} uses | {p.success_count} positive
                            </div>
                          </div>
                          <div className="w-16 h-1.5 bg-secondary rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary rounded-full"
                              style={{ width: `${(p.performance_score || 0) * 100}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Teacher Distillations */}
              <Card className="bg-card/80 border-border/60">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Zap className="w-5 h-5 text-[hsl(var(--activity-autonomy))]" /> Cloud Teacher Distillations
                  </CardTitle>
                  <CardDescription>Patterns extracted from cloud model responses for local learning</CardDescription>
                </CardHeader>
                <CardContent>
                  {distillations.length === 0 ? (
                    <div className="text-center py-6 text-muted-foreground">
                      <Brain className="w-8 h-8 mx-auto mb-2 opacity-30" />
                      <p className="text-sm">No distillations yet. Use cloud models to start learning.</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {distillations.map((d, i) => (
                        <div key={d._id || i} className="p-2 rounded-lg bg-secondary/30">
                          <div className="flex items-center gap-2 mb-1">
                            <Badge variant="outline" className="text-[10px] font-mono-ombra">{d.provider}</Badge>
                            <span className="text-[10px] text-muted-foreground">{d.timestamp ? new Date(d.timestamp).toLocaleString() : ''}</span>
                          </div>
                          <p className="text-xs text-muted-foreground truncate">{d.task_signature}</p>
                          {d.extracted_rules?.length > 0 && (
                            <div className="flex gap-1 mt-1 flex-wrap">
                              {d.extracted_rules.map((r, ri) => (
                                <Badge key={ri} variant="outline" className="text-[9px] text-[hsl(var(--activity-autonomy))]">{r}</Badge>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}

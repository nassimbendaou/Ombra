import React from 'react';
import { Badge } from './ui/badge';
import { Cpu, Cloud, Sparkles, Globe } from 'lucide-react';

const providerConfig = {
  ollama: { icon: Cpu, label: 'Ollama', color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' },
  openai: { icon: Sparkles, label: 'OpenAI', color: 'bg-sky-500/20 text-sky-400 border-sky-500/30' },
  anthropic: { icon: Cloud, label: 'Anthropic', color: 'bg-orange-500/20 text-orange-400 border-orange-500/30' },
  gemini: { icon: Globe, label: 'Gemini', color: 'bg-violet-500/20 text-violet-400 border-violet-500/30' },
};

export default function ModelBadge({ provider, model }) {
  const config = providerConfig[provider] || providerConfig.ollama;
  const Icon = config.icon;

  return (
    <Badge
      variant="outline"
      className={`font-mono-ombra text-[11px] px-2 py-0.5 ${config.color} border`}
      data-testid="chat-model-badge"
    >
      <Icon className="w-3 h-3 mr-1" />
      {config.label}
      {model && <span className="ml-1 opacity-60">({model})</span>}
    </Badge>
  );
}

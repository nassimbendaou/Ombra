import React from 'react';
import { motion } from 'framer-motion';
import ModelBadge from './ModelBadge';
import { User, Zap, Clock } from 'lucide-react';

export default function MessageBubble({ message, showReasoning = false }) {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}
      data-testid="chat-message-bubble"
    >
      {/* Avatar */}
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
        isUser ? 'bg-secondary/60' : 'bg-primary/20'
      }`}>
        {isUser ? <User className="w-4 h-4" /> : <Zap className="w-4 h-4 text-primary" />}
      </div>

      {/* Content */}
      <div className={`max-w-[75%] space-y-1.5 ${isUser ? 'items-end' : ''}`}>
        <div className={`rounded-xl px-4 py-3 ${
          isUser
            ? 'bg-secondary/60 border border-border/60'
            : 'bg-card/70 border border-border/60'
        }`}>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Meta row */}
        <div className={`flex items-center gap-2 text-xs text-muted-foreground font-mono-ombra ${isUser ? 'justify-end' : ''}`}>
          {message.timestamp && (
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
          {isAssistant && message.provider && (
            <ModelBadge provider={message.provider} model={message.model} />
          )}
          {isAssistant && message.routing && showReasoning && (
            <span className="text-[10px] text-muted-foreground/60">
              Score: {message.routing.score} | Route: {message.routing.route}
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}

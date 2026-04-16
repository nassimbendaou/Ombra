import React from 'react';
import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
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
          {isUser ? (
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="text-sm leading-relaxed prose prose-invert prose-sm max-w-none
              prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5
              prose-headings:mt-3 prose-headings:mb-1
              prose-a:text-primary prose-a:no-underline hover:prose-a:underline
              prose-code:text-primary/90 prose-code:bg-primary/10 prose-code:px-1 prose-code:rounded
              prose-pre:bg-black/40 prose-pre:border prose-pre:border-border/40 prose-pre:rounded-lg">
              <ReactMarkdown remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ href, children }) => (
                    <a href={href} target="_blank" rel="noopener noreferrer"
                       className="text-primary hover:underline break-all">
                      {children}
                    </a>
                  ),
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
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

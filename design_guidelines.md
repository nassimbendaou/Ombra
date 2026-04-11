{
  "brand": {
    "product_name": "Ombra",
    "attributes": [
      "premium",
      "minimalist",
      "developer-first",
      "transparent",
      "proactive",
      "calm-intense (quiet dark surfaces + precise glow)"
    ],
    "north_star": "Make autonomy feel safe: always show what the agent is doing, why, and what it will do next—without visual noise."
  },
  "inspiration_refs": {
    "design_personality_refs": [
      {
        "title": "Muzli — Best dashboard design examples (2026)",
        "url": "https://muz.li/blog/best-dashboard-design-examples-inspirations-for-2026/",
        "takeaways": [
          "Deep dark surfaces + soft elevation",
          "Sparse, high-contrast typography",
          "Data cards with clear hierarchy"
        ]
      },
      {
        "title": "Dribbble — dark dashboard tag",
        "url": "https://dribbble.com/tags/dark-dashboard",
        "takeaways": [
          "Glowing status dots",
          "Compact side nav + wide content",
          "Badge-driven metadata"
        ]
      },
      {
        "title": "Atlassian AI transparency principles",
        "url": "https://www.atlassian.com/trust/ai/transparency",
        "takeaways": [
          "Explainability patterns",
          "User control + auditability"
        ]
      }
    ],
    "color_typography_refs": [
      {
        "title": "Transformative Teal (Color of 2026) palette ideas",
        "url": "https://www.wearemydesign.com/post/transformative-teal-colour-palettes",
        "takeaways": [
          "Teal as calm premium accent",
          "Pairs well with graphite neutrals"
        ]
      },
      {
        "title": "Google Fonts — Space Grotesk",
        "url": "https://fonts.google.com/specimen/Space+Grotesk",
        "takeaways": [
          "Crisp UI type with technical vibe",
          "Great numerals for logs/stats"
        ]
      }
    ]
  },
  "visual_style": {
    "style_mix": [
      "Swiss-style grid discipline",
      "Minimal dark SaaS",
      "Subtle glassmorphism for secondary surfaces",
      "Terminal-inspired micro-details (monospace for IDs/timestamps)"
    ],
    "do_not": [
      "No purple-forward gradients",
      "No neon overload; glow is a hint, not a flood",
      "No centered page layouts; keep left-aligned reading flow",
      "No heavy 3D backgrounds; performance first"
    ]
  },
  "typography": {
    "font_pairing": {
      "ui": {
        "family": "Space Grotesk",
        "fallback": "ui-sans-serif, system-ui",
        "usage": "All UI headings, labels, buttons"
      },
      "mono": {
        "family": "IBM Plex Mono",
        "fallback": "ui-monospace, SFMono-Regular",
        "usage": "Timestamps, model IDs, tool call payload snippets"
      }
    },
    "google_fonts_import": {
      "instructions": "In /app/frontend/src/index.css add @import for fonts at the very top (before tailwind layers).",
      "css": "@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');"
    },
    "type_scale_tailwind": {
      "h1": "text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight",
      "h2": "text-base md:text-lg font-medium text-muted-foreground",
      "section_title": "text-sm font-semibold tracking-wide uppercase text-muted-foreground",
      "card_title": "text-base font-semibold",
      "body": "text-sm md:text-base leading-relaxed",
      "mono_small": "font-mono text-xs text-muted-foreground"
    }
  },
  "color_system": {
    "notes": [
      "Dark theme primary. Use teal/cyan glow accents for status + primary actions.",
      "Keep gradients decorative only (<=20% viewport).",
      "Activity types are color-coded via semantic tokens (not arbitrary per component)."
    ],
    "design_tokens_css": {
      "instructions": "Replace :root and .dark tokens in /app/frontend/src/index.css with these values (keep Tailwind layers).",
      "css": ":root {\n  --background: 210 20% 98%;\n  --foreground: 222 47% 11%;\n  --card: 0 0% 100%;\n  --card-foreground: 222 47% 11%;\n  --popover: 0 0% 100%;\n  --popover-foreground: 222 47% 11%;\n  --primary: 188 72% 34%;\n  --primary-foreground: 210 40% 98%;\n  --secondary: 210 40% 96%;\n  --secondary-foreground: 222 47% 11%;\n  --muted: 210 40% 96%;\n  --muted-foreground: 215 16% 46%;\n  --accent: 188 72% 34%;\n  --accent-foreground: 210 40% 98%;\n  --destructive: 0 72% 51%;\n  --destructive-foreground: 210 40% 98%;\n  --border: 214 32% 91%;\n  --input: 214 32% 91%;\n  --ring: 188 72% 34%;\n  --radius: 0.75rem;\n\n  /* Ombra semantic extras */\n  --surface-0: 210 20% 98%;\n  --surface-1: 0 0% 100%;\n  --surface-2: 210 40% 96%;\n  --shadow-color: 222 47% 11%;\n\n  --status-ok: 158 64% 40%;\n  --status-warn: 38 92% 50%;\n  --status-err: 0 72% 51%;\n  --status-info: 188 72% 34%;\n\n  --activity-model: 188 72% 34%;\n  --activity-tool: 158 64% 40%;\n  --activity-memory: 38 92% 50%;\n  --activity-autonomy: 200 90% 55%;\n}\n\n.dark {\n  --background: 220 18% 6%;\n  --foreground: 210 40% 98%;\n  --card: 220 18% 8%;\n  --card-foreground: 210 40% 98%;\n  --popover: 220 18% 8%;\n  --popover-foreground: 210 40% 98%;\n\n  /* Primary accent: Transformative Teal-ish */\n  --primary: 188 72% 42%;\n  --primary-foreground: 220 18% 8%;\n\n  --secondary: 220 16% 12%;\n  --secondary-foreground: 210 40% 98%;\n  --muted: 220 16% 12%;\n  --muted-foreground: 215 20% 70%;\n  --accent: 220 16% 12%;\n  --accent-foreground: 210 40% 98%;\n\n  --destructive: 0 72% 51%;\n  --destructive-foreground: 210 40% 98%;\n\n  --border: 220 14% 18%;\n  --input: 220 14% 18%;\n  --ring: 188 72% 42%;\n\n  /* Ombra semantic extras */\n  --surface-0: 220 18% 6%;\n  --surface-1: 220 18% 8%;\n  --surface-2: 220 16% 12%;\n  --shadow-color: 220 40% 2%;\n\n  --status-ok: 158 64% 44%;\n  --status-warn: 38 92% 54%;\n  --status-err: 0 72% 56%;\n  --status-info: 188 72% 42%;\n\n  --activity-model: 188 72% 42%;\n  --activity-tool: 158 64% 44%;\n  --activity-memory: 38 92% 54%;\n  --activity-autonomy: 200 90% 60%;\n\n  /* Charts (keep subtle, not rainbow) */\n  --chart-1: 188 72% 42%;\n  --chart-2: 158 64% 44%;\n  --chart-3: 38 92% 54%;\n  --chart-4: 200 90% 60%;\n  --chart-5: 215 20% 70%;\n}"
    },
    "tailwind_usage_examples": {
      "page_bg": "bg-background text-foreground",
      "panel_bg": "bg-card/80 backdrop-blur supports-[backdrop-filter]:bg-card/60",
      "hairline_border": "border border-border/60",
      "muted_text": "text-muted-foreground",
      "primary_cta": "bg-primary text-primary-foreground hover:bg-primary/90",
      "focus_ring": "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    },
    "glow_recipes": {
      "teal_glow": "shadow-[0_0_0_1px_hsl(var(--border)/0.6),0_0_24px_hsl(var(--primary)/0.18)]",
      "status_dot_glow": "shadow-[0_0_0_1px_hsl(var(--border)/0.6),0_0_18px_hsl(var(--status-info)/0.35)]",
      "danger_glow": "shadow-[0_0_0_1px_hsl(var(--border)/0.6),0_0_18px_hsl(var(--status-err)/0.25)]"
    },
    "allowed_gradients": {
      "rule": "Decorative only; never on text-heavy surfaces; never >20% viewport; never on small UI elements.",
      "hero_overlay": "bg-[radial-gradient(900px_circle_at_20%_0%,hsl(var(--primary)/0.18),transparent_55%),radial-gradient(700px_circle_at_80%_10%,hsl(var(--activity-autonomy)/0.12),transparent_60%)]"
    }
  },
  "layout_grid": {
    "app_shell": {
      "desktop": "Left sidebar (72px collapsed / 260px expanded) + top command bar + content.",
      "content_max_width": "max-w-[1400px] (centered within content area only; not global text-align)",
      "page_padding": "px-4 sm:px-6 lg:px-8 py-6",
      "grid": "Use 12-col grid on desktop: grid-cols-12 gap-4 lg:gap-6. Cards typically span 3/4/6/8/12.",
      "mobile": "Sidebar becomes Sheet/Drawer; top bar stays; content is single column with stacked cards."
    },
    "dashboard_composition": [
      "Row 1: Daily Summary (8 cols) + System Status (4 cols)",
      "Row 2: Current Tasks (6 cols) + Agent Decision Logs (6 cols)",
      "Row 3: Activity Timeline preview (8 cols) + Quick Actions (4 cols)"
    ]
  },
  "components": {
    "component_path": {
      "navigation": [
        "/app/frontend/src/components/ui/sheet.jsx",
        "/app/frontend/src/components/ui/navigation-menu.jsx",
        "/app/frontend/src/components/ui/tooltip.jsx",
        "/app/frontend/src/components/ui/separator.jsx"
      ],
      "surfaces": [
        "/app/frontend/src/components/ui/card.jsx",
        "/app/frontend/src/components/ui/scroll-area.jsx",
        "/app/frontend/src/components/ui/resizable.jsx"
      ],
      "inputs": [
        "/app/frontend/src/components/ui/input.jsx",
        "/app/frontend/src/components/ui/textarea.jsx",
        "/app/frontend/src/components/ui/switch.jsx",
        "/app/frontend/src/components/ui/checkbox.jsx",
        "/app/frontend/src/components/ui/select.jsx",
        "/app/frontend/src/components/ui/slider.jsx"
      ],
      "feedback": [
        "/app/frontend/src/components/ui/badge.jsx",
        "/app/frontend/src/components/ui/progress.jsx",
        "/app/frontend/src/components/ui/skeleton.jsx",
        "/app/frontend/src/components/ui/sonner.jsx",
        "/app/frontend/src/components/ui/alert.jsx",
        "/app/frontend/src/components/ui/alert-dialog.jsx"
      ],
      "data_display": [
        "/app/frontend/src/components/ui/table.jsx",
        "/app/frontend/src/components/ui/tabs.jsx",
        "/app/frontend/src/components/ui/collapsible.jsx",
        "/app/frontend/src/components/ui/accordion.jsx",
        "/app/frontend/src/components/ui/hover-card.jsx"
      ]
    },
    "page_level_patterns": {
      "dashboard": {
        "key_blocks": [
          {
            "name": "Daily Summary Card",
            "description": "Large card with 2-column inner grid: left narrative summary, right mini-stats + sparkline placeholder.",
            "shadcn": ["card", "badge", "separator"],
            "data_testids": [
              "dashboard-daily-summary-card",
              "dashboard-daily-summary-text",
              "dashboard-daily-summary-stats"
            ]
          },
          {
            "name": "System Status Panel",
            "description": "Stacked status rows with glowing dots (Ollama, Cloud fallback, Memory, Autonomy).",
            "shadcn": ["card", "badge", "tooltip"],
            "data_testids": [
              "dashboard-system-status-panel",
              "system-status-ollama",
              "system-status-cloud",
              "system-status-memory",
              "system-status-autonomy"
            ]
          },
          {
            "name": "Current Tasks",
            "description": "Task list with progress + next action; each row has status pill + subtle hover reveal actions.",
            "shadcn": ["card", "progress", "button", "dropdown-menu"],
            "data_testids": [
              "dashboard-current-tasks-card",
              "task-row",
              "task-row-open-button"
            ]
          }
        ]
      },
      "chat": {
        "layout": "Two-pane: messages (left) + right inspector (Reasoning/Tools/Memory) using Resizable. On mobile, inspector becomes Drawer.",
        "message_bubble": {
          "assistant": "bg-card/70 border border-border/60 rounded-xl px-4 py-3",
          "user": "bg-secondary/60 border border-border/60 rounded-xl px-4 py-3",
          "meta_row": "flex items-center gap-2 text-xs text-muted-foreground font-mono"
        },
        "transparent_reasoning_toggle": {
          "pattern": "A top-right toggle in the inspector header: Tabs = [Reasoning, Tools, Memory]. Reasoning content is Collapsible with 'Show reasoning' switch.",
          "warning": "Do not reveal chain-of-thought if policy requires; show summarized rationale instead. UI still supports toggle.",
          "data_testids": [
            "chat-reasoning-toggle",
            "chat-inspector-tabs",
            "chat-model-badge"
          ]
        },
        "tool_call_cards": {
          "pattern": "Each tool call renders as a Card with header: tool name + status badge + duration; body: key-value table; footer: 'View payload' Collapsible.",
          "shadcn": ["card", "badge", "collapsible", "table", "button"],
          "data_testids": [
            "chat-tool-call-card",
            "chat-tool-call-view-payload-button"
          ]
        },
        "composer": {
          "pattern": "Sticky bottom composer with Textarea + model selector + send button. Add subtle top border + blur.",
          "shadcn": ["textarea", "button", "select"],
          "data_testids": [
            "chat-composer-textarea",
            "chat-composer-send-button",
            "chat-composer-model-select"
          ]
        }
      },
      "permissions": {
        "pattern": "Permission cards with Switch + rationale + last-used timestamp. Dangerous permissions require AlertDialog confirmation.",
        "shadcn": ["card", "switch", "alert-dialog", "badge"],
        "data_testids": [
          "permissions-terminal-switch",
          "permissions-filesystem-switch",
          "permissions-telegram-switch",
          "permissions-confirm-dialog"
        ]
      },
      "activity_timeline": {
        "pattern": "Filter bar (ToggleGroup) + timeline list (ScrollArea). Each entry: left colored rail + icon + title + meta + expandable details.",
        "filters": ["all", "model", "tool", "memory", "autonomy"],
        "shadcn": ["toggle-group", "scroll-area", "collapsible", "badge", "tooltip"],
        "data_testids": [
          "activity-filter-toggle-group",
          "activity-timeline-list",
          "activity-timeline-item",
          "activity-item-expand-button"
        ],
        "color_coding": {
          "model": "border-l-[3px] border-l-[hsl(var(--activity-model))]",
          "tool": "border-l-[3px] border-l-[hsl(var(--activity-tool))]",
          "memory": "border-l-[3px] border-l-[hsl(var(--activity-memory))]",
          "autonomy": "border-l-[3px] border-l-[hsl(var(--activity-autonomy))]"
        }
      },
      "settings": {
        "pattern": "Tabbed settings: [Runtime, Models, Learning, Privacy]. Each tab is a Form with grouped Cards.",
        "shadcn": ["tabs", "form", "input", "select", "slider", "switch", "button"],
        "data_testids": [
          "settings-tabs",
          "settings-ollama-host-input",
          "settings-model-preference-select",
          "settings-learning-switch",
          "settings-save-button"
        ]
      }
    },
    "badges_and_status": {
      "model_badge": {
        "pattern": "Small Badge with provider icon + model name. Use mono font for model id.",
        "classes": "font-mono text-[11px] px-2 py-0.5 rounded-md bg-secondary/60 border border-border/60",
        "providers": {
          "ollama": "bg-secondary/60",
          "openai": "bg-secondary/60",
          "anthropic": "bg-secondary/60",
          "gemini": "bg-secondary/60"
        }
      },
      "status_indicator": {
        "pattern": "Dot + label. Dot uses semantic color + glow. States: idle, thinking, executing, done, error.",
        "dot_classes": {
          "thinking": "bg-[hsl(var(--status-info))] shadow-[0_0_18px_hsl(var(--status-info)/0.35)]",
          "executing": "bg-[hsl(var(--activity-autonomy))] shadow-[0_0_18px_hsl(var(--activity-autonomy)/0.30)]",
          "done": "bg-[hsl(var(--status-ok))] shadow-[0_0_18px_hsl(var(--status-ok)/0.25)]",
          "error": "bg-[hsl(var(--status-err))] shadow-[0_0_18px_hsl(var(--status-err)/0.25)]"
        },
        "data_testids": ["agent-status-indicator"]
      }
    }
  },
  "motion_microinteractions": {
    "principles": [
      "Fast UI: 120–180ms for hover/focus, 180–240ms for panel open/close.",
      "Use opacity/translate/blur for entrances; avoid layout thrash.",
      "Respect prefers-reduced-motion."
    ],
    "recommended_library": {
      "name": "framer-motion",
      "why": "Lightweight for micro-animations (panel enter, list item reveal, status pulse).",
      "install": "npm i framer-motion",
      "usage_snippets_js": [
        "import { motion, AnimatePresence } from 'framer-motion';",
        "<motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 6 }} transition={{ duration: 0.18 }} />"
      ]
    },
    "interaction_specs": {
      "sidebar_nav_item": {
        "hover": "bg-secondary/50",
        "active": "bg-secondary/70 border border-border/60",
        "motion": "icon shifts x by 2px on hover (transform only on icon)"
      },
      "cards": {
        "hover": "border-border/80 + subtle teal glow",
        "classes": "transition-colors duration-200 hover:border-border/80 hover:shadow-[0_0_0_1px_hsl(var(--border)/0.6),0_0_24px_hsl(var(--primary)/0.12)]"
      },
      "status_pulse": {
        "pattern": "Use CSS keyframes for a gentle pulse on thinking/executing dots.",
        "css": "@keyframes ombra-pulse { 0%,100% { opacity: 1; } 50% { opacity: .55; } }",
        "classes": "animate-[ombra-pulse_1.2s_ease-in-out_infinite]"
      }
    }
  },
  "data_viz": {
    "library": {
      "name": "recharts",
      "install": "npm i recharts",
      "usage": "Use for tiny sparklines in dashboard cards only. Keep strokes 1.5–2px, muted gridlines, no gradients."
    },
    "empty_states": {
      "pattern": "Skeleton first, then empty state with concise copy + secondary action.",
      "copy_tone": "Calm, factual, proactive (e.g., 'No tool calls yet today. Run a task to start logging activity.')"
    }
  },
  "accessibility": {
    "requirements": [
      "WCAG AA contrast: muted text still readable on dark surfaces.",
      "Visible focus rings on all interactive elements.",
      "Keyboard navigation: sidebar, tabs, toggle groups, dialogs.",
      "prefers-reduced-motion: disable pulses and entrance animations."
    ],
    "aria_notes": [
      "Switches must have labels and descriptions.",
      "Timeline items expandable sections must use button with aria-expanded."
    ]
  },
  "images": {
    "image_urls": [
      {
        "category": "app-shell-background (decorative)",
        "description": "Optional subtle background image for the top hero strip / header area only (<=20% viewport). Use as a low-opacity overlay behind the command bar.",
        "url": "https://images.unsplash.com/photo-1707209856577-eeea3627f8bf?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODh8MHwxfHNlYXJjaHwxfHxkYXJrJTIwYWJzdHJhY3QlMjB0ZWFsJTIwbm9pc2UlMjBncmFkaWVudCUyMGJhY2tncm91bmR8ZW58MHx8fHRlYWx8MTc3NTkyMzM1OHww&ixlib=rb-4.1..0&q=85"
      },
      {
        "category": "timeline-empty-state (decorative)",
        "description": "Abstract texture for empty timeline panel background (very subtle, 6–10% opacity).",
        "url": "https://images.pexels.com/photos/11927240/pexels-photo-11927240.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
      },
      {
        "category": "settings-header (decorative)",
        "description": "Starfield-like subtle image for settings header strip (<=15% viewport).",
        "url": "https://images.unsplash.com/photo-1557688543-4e2f83d6796b?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODh8MHwxfHNlYXJjaHwzfHxkYXJrJTIwYWJzdHJhY3QlMjB0ZWFsJTIwbm9pc2UlMjBncmFkaWVudCUyMGJhY2tncm91bmR8ZW58MHx8fHRlYWx8MTc3NTkyMzM1OHww&ixlib=rb-4.1.0&q=85"
      }
    ]
  },
  "implementation_notes_js": {
    "react_files": "Project uses .js (not .tsx). Keep components in .jsx only if existing pattern; otherwise follow repo conventions.",
    "data_testid_rule": "Every button/input/toggle/tab/filter/message item/tool card must include data-testid in kebab-case.",
    "app_css_cleanup": {
      "note": "Remove default CRA centered header styles from App.css; do not center align the app container.",
      "recommended": "Keep App.css minimal or delete unused .App-header styles; rely on Tailwind + tokens."
    }
  },
  "instructions_to_main_agent": [
    "Set dark mode as default by adding className='dark' on the root html/body wrapper (or via ThemeProvider if present).",
    "Replace index.css tokens with the provided Ombra tokens and add Google Fonts import.",
    "Build an AppShell: Sidebar + Top Command Bar + Content. Use Sheet for mobile nav.",
    "Chat page: implement Resizable split (messages + inspector). Inspector uses Tabs and Collapsible for reasoning/tool payloads.",
    "Activity Timeline: ToggleGroup filters + ScrollArea list; each item uses left colored rail based on type tokens.",
    "Permissions: Switches with rationale text; dangerous toggles require AlertDialog confirmation.",
    "Add micro-interactions: card hover glow, status dot pulse, panel enter transitions (Framer Motion).",
    "Ensure performance: avoid large animated gradients; keep decorative overlays to header strips only.",
    "Add data-testid attributes everywhere interactive/critical per guideline."
  ],
  "general_ui_ux_design_guidelines_appendix": "<General UI UX Design Guidelines>\n    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms\n    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text\n   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json\n\n **GRADIENT RESTRICTION RULE**\nNEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc\nNEVER use dark gradients for logo, testimonial, footer etc\nNEVER let gradients cover more than 20% of the viewport.\nNEVER apply gradients to text-heavy content or reading areas.\nNEVER use gradients on small UI elements (<100px width).\nNEVER stack multiple gradient layers in the same viewport.\n\n**ENFORCEMENT RULE:**\n    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors\n\n**How and where to use:**\n   • Section backgrounds (not content backgrounds)\n   • Hero section header content. Eg: dark to light to dark color\n   • Decorative overlays and accent elements only\n   • Hero section with 2-3 mild color\n   • Gradients creation can be done for any angle say horizontal, vertical or diagonal\n\n- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**\n\n</Font Guidelines>\n\n- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. \n   \n- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.\n\n- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.\n   \n- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly\n    Eg: - if it implies playful/energetic, choose a colorful scheme\n           - if it implies monochrome/minimal, choose a black–white/neutral scheme\n\n**Component Reuse:**\n\t- Prioritize using pre-existing components from src/components/ui when applicable\n\t- Create new components that match the style and conventions of existing components when needed\n\t- Examine existing components to understand the project's component patterns before creating new ones\n\n**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component\n\n**Best Practices:**\n\t- Use Shadcn/UI as the primary component library for consistency and accessibility\n\t- Import path: ./components/[component-name]\n\n**Export Conventions:**\n\t- Components MUST use named exports (export const ComponentName = ...)\n\t- Pages MUST use default exports (export default function PageName() {...})\n\n**Toasts:**\n  - Use `sonner` for toasts\"\n  - Sonner component are located in `/app/src/components/ui/sonner.tsx`\n\nUse 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals.\n</General UI UX Design Guidelines>"
}

"""
Ombra Context Engine
====================
Smart relevance scoring: decides which files, memories, and context
matter most for a given task. Feeds the agent loop with optimally
curated context instead of brute-force token stuffing.
"""

import re
import time
from typing import Optional
from collections import defaultdict


class ContextEngine:
    """
    Scores and ranks context candidates (files, memories, conversation turns)
    based on relevance to the current query. Produces a trimmed context
    window that fits within token budgets.
    """

    def __init__(self, max_context_tokens: int = 12000):
        self.max_context_tokens = max_context_tokens
        self._recency_weight = 0.25
        self._relevance_weight = 0.45
        self._frequency_weight = 0.15
        self._dependency_weight = 0.15

    def score_files(self, query: str, file_graph, rag_results: list[dict],
                    active_files: list[str] = None) -> list[dict]:
        """
        Score files for relevance to a query.
        Combines:
          - RAG semantic similarity score
          - File dependency proximity (imports/importers)
          - Recency of access
          - Active file bonus (files the user recently opened/modified)
        """
        scores: dict[str, float] = defaultdict(float)
        file_meta: dict[str, dict] = {}

        # RAG semantic scores
        for result in rag_results:
            filepath = result.get("file", "")
            if filepath:
                scores[filepath] += result.get("score", 0) * self._relevance_weight
                file_meta[filepath] = result

        # Active file bonus
        for fp in (active_files or []):
            scores[fp] += 0.3

        # Dependency proximity: if a high-scoring file imports/is-imported-by others, boost them
        if file_graph:
            top_files = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
            for fp, sc in top_files:
                related = file_graph.get_related_files(fp, depth=1)
                for rel in related:
                    scores[rel] += sc * self._dependency_weight * 0.5

        # Sort by score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [
            {"file": fp, "score": round(sc, 4), "meta": file_meta.get(fp, {})}
            for fp, sc in ranked
        ]

    def score_memories(self, query: str, memories: list[dict],
                       rag_results: list[dict] = None) -> list[dict]:
        """
        Score memories for relevance to a query.
        Combines:
          - RAG semantic similarity
          - Utility score (from memory system)
          - Recency decay
          - Keyword overlap
        """
        scores: dict[int, float] = {}  # index -> score

        # Keyword overlap scoring
        query_words = set(re.findall(r'\w+', query.lower()))

        for i, mem in enumerate(memories):
            score = 0.0
            content = mem.get("content", "")
            content_words = set(re.findall(r'\w+', content.lower()))

            # Keyword overlap
            overlap = len(query_words & content_words)
            if query_words:
                score += (overlap / len(query_words)) * 0.3

            # Utility score from memory system
            score += mem.get("utility_score", 0.5) * 0.3

            # Recency (newer = better)
            age_seconds = mem.get("age_seconds", 86400)
            recency = max(0, 1.0 - (age_seconds / (7 * 86400)))  # 0-1 over 7 days
            score += recency * self._recency_weight

            scores[i] = score

        # Add RAG results boost
        if rag_results:
            for result in rag_results:
                if result.get("type") == "memory":
                    # Find matching memory by content preview
                    preview = result.get("_text", "")
                    for i, mem in enumerate(memories):
                        if mem.get("content", "")[:200] == preview:
                            scores[i] = scores.get(i, 0) + result.get("score", 0) * self._relevance_weight
                            break

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [
            {"memory": memories[i], "score": round(sc, 4), "index": i}
            for i, sc in ranked if i < len(memories)
        ]

    def score_conversation_turns(self, query: str, turns: list[dict]) -> list[dict]:
        """
        Score conversation turns for relevance.
        Recent turns get higher weight, but semantically relevant older turns
        are also included.
        """
        query_words = set(re.findall(r'\w+', query.lower()))
        scored = []

        for i, turn in enumerate(turns):
            content = turn.get("content", "")
            content_words = set(re.findall(r'\w+', content.lower()))

            # Keyword relevance
            overlap = len(query_words & content_words) if query_words else 0
            relevance = (overlap / len(query_words)) if query_words else 0

            # Recency: more recent turns score higher (linear decay)
            recency = (i + 1) / len(turns) if turns else 0

            # Role weight: user messages slightly more important for context
            role_weight = 1.1 if turn.get("role") == "user" else 1.0

            score = (relevance * 0.5 + recency * 0.4 + 0.1) * role_weight
            scored.append({"turn": turn, "score": round(score, 4), "index": i})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    def build_context(self, query: str, *,
                      files: list[dict] = None,
                      memories: list[dict] = None,
                      turns: list[dict] = None,
                      file_graph=None,
                      rag_results: list[dict] = None,
                      active_files: list[str] = None,
                      max_tokens: int = None) -> dict:
        """
        Build an optimally curated context window for the agent.
        Returns a dict with scored+trimmed context sections.
        """
        max_tokens = max_tokens or self.max_context_tokens
        budget = max_tokens
        context = {"files": [], "memories": [], "turns": [], "total_tokens_est": 0}

        # Score everything
        scored_files = self.score_files(query, file_graph, rag_results or [], active_files) if files else []
        scored_memories = self.score_memories(query, memories or [], rag_results) if memories else []
        scored_turns = self.score_conversation_turns(query, turns or []) if turns else []

        # Allocate budget: 40% files, 25% memories, 35% conversation
        file_budget = int(budget * 0.4)
        memory_budget = int(budget * 0.25)
        turn_budget = int(budget * 0.35)

        # Pick top scored items within budget
        tokens_used = 0
        for sf in scored_files[:10]:
            est_tokens = len(sf.get("meta", {}).get("_text", "")) // 4
            if tokens_used + est_tokens > file_budget:
                break
            context["files"].append(sf)
            tokens_used += est_tokens

        for sm in scored_memories[:10]:
            content = sm.get("memory", {}).get("content", "")
            est_tokens = len(content) // 4
            if tokens_used + est_tokens > file_budget + memory_budget:
                break
            context["memories"].append(sm)
            tokens_used += est_tokens

        for st in scored_turns[:15]:
            content = st.get("turn", {}).get("content", "")
            est_tokens = len(content) // 4
            if tokens_used + est_tokens > budget:
                break
            context["turns"].append(st)
            tokens_used += est_tokens

        context["total_tokens_est"] = tokens_used
        return context

    def format_context_for_prompt(self, context: dict) -> str:
        """Convert scored context into a formatted string for the system prompt."""
        parts = []

        if context.get("files"):
            parts.append("## Relevant Code Files")
            for f in context["files"][:5]:
                meta = f.get("meta", {})
                parts.append(f"- `{f['file']}` (relevance: {f['score']:.2f})")
                if meta.get("_text"):
                    parts.append(f"  ```\n  {meta['_text'][:300]}\n  ```")

        if context.get("memories"):
            parts.append("\n## Relevant Memories")
            for m in context["memories"][:5]:
                mem = m.get("memory", {})
                parts.append(f"- [{mem.get('type', 'fact')}] {mem.get('content', '')[:200]}")

        if context.get("turns"):
            parts.append("\n## Recent Conversation Context")
            sorted_turns = sorted(context["turns"], key=lambda x: x.get("index", 0))
            for t in sorted_turns[:8]:
                turn = t.get("turn", {})
                role = turn.get("role", "user")
                content = turn.get("content", "")[:300]
                parts.append(f"  {role}: {content}")

        return "\n".join(parts)


# ── Global instance ───────────────────────────────────────────────────────────
context_engine = ContextEngine()

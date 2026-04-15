"""
Ombra RAG Engine
================
Vector embeddings + semantic search over code, documents, and memories.
Uses sentence-transformers for local embedding generation and
FAISS for fast similarity search.
"""

import os
import json
import time
import hashlib
import numpy as np
from typing import Optional
from pathlib import Path

# Lazy imports — these are heavy, only load when needed
_model = None
_faiss_index = None

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
CHUNK_SIZE = 512       # characters per chunk
CHUNK_OVERLAP = 64     # overlap between chunks
MAX_FILE_SIZE = 256 * 1024  # 256 KB


def _get_model():
    """Lazy-load the sentence-transformer model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(EMBEDDING_MODEL)
        except ImportError:
            raise RuntimeError(
                "sentence-transformers not installed. Run: pip install sentence-transformers"
            )
    return _model


def embed_texts(texts: list[str], batch_size: int = 64) -> np.ndarray:
    """Generate embeddings for a list of texts. Returns (N, 384) array."""
    model = _get_model()
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False, normalize_embeddings=True)
    return np.array(embeddings, dtype=np.float32)


def embed_single(text: str) -> np.ndarray:
    """Embed a single text string."""
    return embed_texts([text])[0]


# ── Text Chunking ─────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start = end - overlap
    return chunks


def chunk_code(source: str, filepath: str = "") -> list[dict]:
    """
    Smart code chunking: split by functions/classes where possible,
    fall back to line-based chunks.
    """
    lines = source.split("\n")
    chunks = []
    current_chunk = []
    current_start = 1

    # Detect function/class boundaries for Python/JS
    boundary_re = None
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".py":
        import re
        boundary_re = re.compile(r'^(?:class |def |async def )')
    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        import re
        boundary_re = re.compile(r'^(?:export\s+)?(?:function |class |const \w+ = )')

    for i, line in enumerate(lines, 1):
        if boundary_re and boundary_re.match(line) and current_chunk:
            text = "\n".join(current_chunk)
            if text.strip():
                chunks.append({
                    "text": text,
                    "file": filepath,
                    "start_line": current_start,
                    "end_line": i - 1,
                })
            current_chunk = [line]
            current_start = i
        else:
            current_chunk.append(line)

        # Force split if chunk gets too large
        if len("\n".join(current_chunk)) > CHUNK_SIZE * 2:
            text = "\n".join(current_chunk)
            if text.strip():
                chunks.append({
                    "text": text,
                    "file": filepath,
                    "start_line": current_start,
                    "end_line": i,
                })
            current_chunk = []
            current_start = i + 1

    # Final chunk
    if current_chunk:
        text = "\n".join(current_chunk)
        if text.strip():
            chunks.append({
                "text": text,
                "file": filepath,
                "start_line": current_start,
                "end_line": len(lines),
            })

    return chunks


# ── FAISS Vector Store ────────────────────────────────────────────────────────

class VectorStore:
    """
    FAISS-backed vector store for semantic search.
    Stores embeddings + metadata for retrieval.
    """

    def __init__(self, dimension: int = EMBEDDING_DIM):
        self.dimension = dimension
        self._index = None
        self._metadata: list[dict] = []   # parallel to index rows
        self._id_map: dict[str, int] = {}  # content_hash -> index position

    def _ensure_index(self):
        if self._index is None:
            try:
                import faiss
                self._index = faiss.IndexFlatIP(self.dimension)  # Inner product (cosine with normalized vectors)
            except ImportError:
                raise RuntimeError("faiss-cpu not installed. Run: pip install faiss-cpu")

    def add(self, texts: list[str], metadata_list: list[dict] | None = None,
            embeddings: np.ndarray | None = None) -> int:
        """
        Add texts to the vector store.
        Returns number of new items added (skips duplicates).
        """
        self._ensure_index()

        if embeddings is None:
            embeddings = embed_texts(texts)

        if metadata_list is None:
            metadata_list = [{"text": t} for t in texts]

        added = 0
        new_embeddings = []
        new_metadata = []

        for i, text in enumerate(texts):
            content_hash = hashlib.md5(text.encode()).hexdigest()
            if content_hash in self._id_map:
                continue  # Skip duplicate
            self._id_map[content_hash] = len(self._metadata) + len(new_metadata)
            meta = metadata_list[i] if i < len(metadata_list) else {"text": text}
            meta["_hash"] = content_hash
            meta["_text"] = text[:200]  # Preview
            new_metadata.append(meta)
            new_embeddings.append(embeddings[i])
            added += 1

        if new_embeddings:
            import faiss
            vectors = np.array(new_embeddings, dtype=np.float32)
            self._index.add(vectors)
            self._metadata.extend(new_metadata)

        return added

    def search(self, query: str, top_k: int = 10,
               filter_fn=None) -> list[dict]:
        """
        Semantic search. Returns top-k most similar items.
        Each result includes score, text preview, and metadata.
        """
        self._ensure_index()

        if self._index.ntotal == 0:
            return []

        query_vec = embed_single(query).reshape(1, -1)
        k = min(top_k * 3 if filter_fn else top_k, self._index.ntotal)

        scores, indices = self._index.search(query_vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._metadata):
                continue
            meta = self._metadata[idx]
            if filter_fn and not filter_fn(meta):
                continue
            results.append({
                "score": float(score),
                **meta,
            })
            if len(results) >= top_k:
                break

        return results

    def remove_by_file(self, filepath: str):
        """Remove all entries for a given file. (Rebuilds index)."""
        import faiss
        new_metadata = []
        new_embeddings = []
        removed = 0

        for i, meta in enumerate(self._metadata):
            if meta.get("file") == filepath:
                removed += 1
                self._id_map.pop(meta.get("_hash", ""), None)
                continue
            new_metadata.append(meta)
            # We need to reconstruct the vector
            vec = self._index.reconstruct(i)
            new_embeddings.append(vec)

        if removed:
            self._index = faiss.IndexFlatIP(self.dimension)
            if new_embeddings:
                self._index.add(np.array(new_embeddings, dtype=np.float32))
            self._metadata = new_metadata
            self._id_map = {m["_hash"]: i for i, m in enumerate(new_metadata) if "_hash" in m}

        return removed

    @property
    def size(self) -> int:
        return self._index.ntotal if self._index else 0

    def get_stats(self) -> dict:
        return {
            "total_vectors": self.size,
            "dimension": self.dimension,
            "unique_files": len(set(m.get("file", "") for m in self._metadata)),
        }


# ── Codebase Indexer ──────────────────────────────────────────────────────────

class CodebaseRAG:
    """
    High-level RAG interface: index a codebase directory and
    provide semantic search over it.
    """

    SUPPORTED_EXTS = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
                      ".rs", ".c", ".cpp", ".h", ".rb", ".php", ".md", ".txt"}
    IGNORE_DIRS = {
        "node_modules", ".git", "__pycache__", ".venv", "venv",
        "dist", "build", ".next", ".cache", "target",
    }

    def __init__(self):
        self.code_store = VectorStore()
        self.memory_store = VectorStore()
        self._indexed_files: dict[str, str] = {}  # relpath -> hash

    def index_directory(self, root_dir: str, force: bool = False) -> dict:
        """Index all supported files in a directory."""
        start = time.time()
        files_indexed = 0
        chunks_added = 0
        errors = 0

        for dirpath, dirnames, filenames in os.walk(root_dir):
            dirnames[:] = [d for d in dirnames if d not in self.IGNORE_DIRS]

            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in self.SUPPORTED_EXTS:
                    continue

                fpath = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(fpath, root_dir)

                if os.path.getsize(fpath) > MAX_FILE_SIZE:
                    continue

                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        source = f.read()
                except (IOError, OSError):
                    errors += 1
                    continue

                content_hash = hashlib.md5(source.encode()).hexdigest()
                if not force and self._indexed_files.get(rel_path) == content_hash:
                    continue  # Already indexed, no changes

                # Remove old entries for this file
                self.code_store.remove_by_file(rel_path)

                # Chunk and embed
                chunks = chunk_code(source, rel_path)
                if not chunks:
                    continue

                texts = [c["text"] for c in chunks]
                metadata = [{
                    "file": rel_path,
                    "start_line": c["start_line"],
                    "end_line": c["end_line"],
                    "type": "code",
                } for c in chunks]

                added = self.code_store.add(texts, metadata)
                chunks_added += added
                files_indexed += 1
                self._indexed_files[rel_path] = content_hash

        return {
            "files_indexed": files_indexed,
            "chunks_added": chunks_added,
            "total_vectors": self.code_store.size,
            "errors": errors,
            "duration_ms": int((time.time() - start) * 1000),
        }

    def index_memories(self, memories: list[dict]) -> int:
        """Index memory documents for semantic retrieval."""
        texts = [m.get("content", "") for m in memories if m.get("content")]
        metadata = [{
            "type": "memory",
            "mem_type": m.get("type", "fact"),
            "created_at": m.get("created_at", ""),
        } for m in memories if m.get("content")]
        if not texts:
            return 0
        return self.memory_store.add(texts, metadata)

    def search(self, query: str, top_k: int = 10, scope: str = "all") -> list[dict]:
        """
        Semantic search across code and/or memories.
        scope: 'code', 'memory', or 'all'
        """
        results = []
        if scope in ("code", "all"):
            results.extend(self.code_store.search(query, top_k))
        if scope in ("memory", "all"):
            results.extend(self.memory_store.search(query, top_k))

        # Sort by score descending
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results[:top_k]

    def get_stats(self) -> dict:
        return {
            "code": self.code_store.get_stats(),
            "memory": self.memory_store.get_stats(),
            "indexed_files": len(self._indexed_files),
        }


# ── Global instance ───────────────────────────────────────────────────────────
codebase_rag = CodebaseRAG()

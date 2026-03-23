#!/usr/bin/env python3
"""
Semgrep - Local Semantic Code Search
Uses multiple embedding backends with priority order:
1. llama.cpp (gguf models via llama-cpp-python) - Primary
2. HuggingFace API (router.huggingface.co)
3. ONNX (local runtime)
4. Ollama (fallback)
"""

import os
import sys
import json
import argparse
import hashlib
import struct
import sqlite3
import math
from pathlib import Path
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
import requests
import json
import os

# Embedding cache file
EMBED_CACHE_FILE = os.environ.get("EMBED_CACHE_FILE", "/tmp/semgrepll_cache.json")

def _load_embedding_cache():
    """Load embedding cache from file."""
    try:
        with open(EMBED_CACHE_FILE) as f:
            return json.load(f)
    except:
        return {}

def _save_embedding_cache(cache):
    """Save embedding cache to file."""
    try:
        with open(EMBED_CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except:
        pass

# ============================================================================
# EMBEDDING BACKEND CONFIGURATION
# ============================================================================

# User can override backend: llama/hf/onnx/ollama/auto
EMBED_BACKEND = os.environ.get("EMBED_BACKEND", "auto").lower()

# Model to use (default: mxbai-embed-large-v1)
EMBED_MODEL = os.environ.get("EMBED_MODEL", "mxbai-embed-large-v1")

# llama.cpp config
LLM_MODEL_PATH = os.environ.get("LLM_MODEL_PATH", "")  # Path to GGUF file

# ONNX config
ONNX_MODEL_PATH = os.environ.get("ONNX_MODEL_PATH", "")

# HuggingFace config - use new router endpoint
HF_TOKEN = os.environ.get("HF_TOKEN", "")
HF_MODEL = os.environ.get("HF_MODEL", "mixedbread-ai/mxbai-embed-large-v1")

# Ollama config
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/embeddings")

# ============================================================================
# BACKEND DETECTION AND PRIORITY
# ============================================================================

# Priority order when auto-detecting: llama.cpp > HF API > ONNX > Ollama
BACKEND_PRIORITY = ["llama", "hf", "onnx", "ollama"]

# Global state for backends
_llama_session = None
_onx_session = None
_detected_backends = None


def _detect_available_backends() -> List[str]:
    """Auto-detect available embedding backends based on what's installed/configured."""
    global _detected_backends
    if _detected_backends is not None:
        return _detected_backends
    
    available = []
    
    # 1. Check llama.cpp (gguf model via llama-cpp-python)
    if LLM_MODEL_PATH and os.path.exists(LLM_MODEL_PATH):
        try:
            from llama_cpp import Llama
            available.append("llama")
            print(f"   [Backend] llama.cpp available: {LLM_MODEL_PATH}")
        except ImportError:
            print(f"   [Backend] llama.cpp configured but llama-cpp-python not installed")
    
    # 2. Check HuggingFace API (new router endpoint)
    if HF_TOKEN:
        available.append("hf")
        print(f"   [Backend] HuggingFace API available (token set)")
    
    # 3. Check ONNX runtime
    onnx_path = ONNX_MODEL_PATH or "/root/models/mxbai-embed-large-v1/onnx/model_quantized.onnx"
    if os.path.exists(onnx_path):
        try:
            import onnxruntime as ort
            available.append("onnx")
            print(f"   [Backend] ONNX available: {onnx_path}")
        except ImportError:
            print(f"   [Backend] ONNX model exists but onnxruntime not installed")
    
    # 4. Check Ollama (always available as fallback)
    available.append("ollama")
    print(f"   [Backend] Ollama available (fallback)")
    
    _detected_backends = available
    return available


def _get_backend_order() -> List[str]:
    """Get the ordered list of backends to try based on user config and auto-detection."""
    if EMBED_BACKEND != "auto":
        # User explicitly chose a backend
        if EMBED_BACKEND in ["llama", "hf", "onnx", "ollama"]:
            return [EMBED_BACKEND]
        else:
            print(f"   Warning: Unknown EMBED_BACKEND={EMBED_BACKEND}, using auto")
    
    # Auto-detect and use priority order
    available = _detect_available_backends()
    
    # Filter available backends by priority
    ordered = []
    for backend in BACKEND_PRIORITY:
        if backend in available:
            ordered.append(backend)
    
    return ordered


# ============================================================================
# LAMA.CPP BACKEND (Primary)
# ============================================================================

def _get_llama_session():
    """Get or create llama.cpp session."""
    global _llama_session
    if _llama_session is not None:
        return _llama_session
    
    model_path = LLM_MODEL_PATH
    if not model_path or not os.path.exists(model_path):
        # Try common paths
        common_paths = [
            "/root/models/mxbai-embed-large-v1/mxbai-embed-large-v1-q4_k.gguf",
            "/root/models/mxbai-embed-large-v1/ggml-model-q4_k.gguf",
            "/root/models/gguf/mxbai-embed-large-v1-q4_k.gguf",
        ]
        for p in common_paths:
            if os.path.exists(p):
                model_path = p
                break
    
    if not model_path or not os.path.exists(model_path):
        return None
    
    try:
        from llama_cpp import Llama
        _llama_session = Llama(
            model_path=model_path,
            embedding=True,
            n_ctx=512,
            n_threads=4,
        )
        print(f"   llama.cpp loaded: {model_path}")
        return _llama_session
    except Exception as e:
        print(f"   llama.cpp failed to load: {e}")
        return None


def _llama_embed(text: str) -> List[float]:
    """Get embedding using llama.cpp (gguf model)."""
    session = _get_llama_session()
    if session is None:
        raise Exception("llama.cpp session not available")
    
    try:
        embedding = session.embed(text)
        return embedding
    except Exception as e:
        raise Exception(f"llama.cpp embedding failed: {e}")


# ============================================================================
# HUGGINGFACE API BACKEND (New router endpoint)
# ============================================================================

def _hf_embed(text: str) -> List[float]:
    """Get embedding from HuggingFace Inference API using new router endpoint."""
    try:
        # Use new router endpoint (NOT the deprecated api-inference.huggingface.co)
        API_URL = f"https://router.huggingface.co/hf-inference/models/{HF_MODEL}"
        resp = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {HF_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "inputs": text,
                "truncate": 512
            },
            timeout=30
        )
        resp.raise_for_status()
        embedding = resp.json()
        
        if isinstance(embedding, list) and len(embedding) > 0:
            return embedding
        elif isinstance(embedding, dict) and "embedding" in embedding:
            return embedding["embedding"]
        else:
            raise Exception(f"HF API returned invalid response: {embedding}")
    except Exception as e:
        raise Exception(f"HuggingFace API failed: {e}")


# ============================================================================
# ONNX BACKEND (Local runtime - already implemented)
# ============================================================================

def _get_onnx_session():
    """Get or create ONNX runtime session."""
    global _onx_session
    if _onx_session is not None:
        return _onx_session
    
    try:
        import onnxruntime as ort
        # Try to find model
        model_path = ONNX_MODEL_PATH or "/root/models/mxbai-embed-large-v1/onnx/model_quantized.onnx"
        _onx_session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        print(f"   ONNX loaded: {model_path}")
        return _onx_session
    except Exception as e:
        print(f"   ONNX not available: {e}")
        return None


def _onnx_embed(text: str) -> List[float]:
    """Get embedding using ONNX runtime."""
    import numpy as np
    import json
    
    # Try to load tokenizer
    tokenizer_path = "/root/models/mxbai-embed-large-v1/tokenizer.json"
    try:
        with open(tokenizer_path) as f:
            tok_data = json.load(f)
        vocab = tok_data["model"]["vocab"]
        
        # Simple tokenization
        tokens = []
        for char in text.lower():
            tokens.append(vocab.get(char, 0))
        
        # Pad to 512
        if len(tokens) < 512:
            tokens = tokens + [0] * (512 - len(tokens))
        
        attention_mask = [1] * min(len(text), 512) + [0] * max(0, 512 - len(text))
        token_type_ids = [0] * 512
        
        # Run inference
        sess = _get_onnx_session()
        if sess is None:
            raise Exception("ONNX session not available")
        
        input_ids = np.array([tokens], dtype=np.int64)
        attention_mask = np.array([attention_mask], dtype=np.int64)
        token_type_ids = np.array([token_type_ids], dtype=np.int64)
        
        embeddings = sess.run(None, {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids
        })[0]
        
        # Mean pooling
        mean_embed = np.mean(embeddings, axis=1)[0].tolist()
        return mean_embed
    except Exception as e:
        raise Exception(f"ONNX embedding failed: {e}")


# ============================================================================
# OLLAMA BACKEND (Fallback)
# ============================================================================

def _ollama_embed(text: str) -> List[float]:
    """Get embedding from Ollama."""
    try:
        resp = requests.post(
            OLLAMA_URL, 
            json={"model": EMBED_MODEL, "prompt": text}, 
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
    except Exception as e:
        raise Exception(f"Ollama embedding failed: {e}")


# ============================================================================
# UNIFIED EMBEDDING FUNCTION
# ============================================================================

def get_embedding(text: str, backend: str = None) -> List[float]:
    """
    Get embedding using the configured backend priority order.
    
    Args:
        text: Input text to embed
        backend: Optional override for specific backend
        
    Returns:
        List of embedding floats
    """
    # Check cache first
    cache = _load_embedding_cache()
    text_hash = hashlib.md5(text.encode()).hexdigest()
    if text_hash in cache:
        return cache[text_hash]
    
    embedding = None
    last_error = None
    
    # Determine which backends to try
    if backend:
        backends_to_try = [backend]
    else:
        backends_to_try = _get_backend_order()
    
    print(f"   Trying backends: {backends_to_try}")
    
    for be in backends_to_try:
        try:
            if be == "llama":
                print(f"   [llama.cpp] {text[:30]}...")
                embedding = _llama_embed(text)
            elif be == "hf":
                print(f"   [HF API] {text[:30]}...")
                embedding = _hf_embed(text)
            elif be == "onnx":
                print(f"   [ONNX] {text[:30]}...")
                embedding = _onnx_embed(text)
            elif be == "ollama":
                print(f"   [Ollama] {text[:30]}...")
                embedding = _ollama_embed(text)
            
            if embedding is not None:
                print(f"   [Success] {be} backend succeeded")
                break
        except Exception as e:
            print(f"   [Failed] {be} backend failed: {e}")
            last_error = e
            continue
    
    if embedding is None:
        raise Exception(f"All embedding backends failed. Last error: {last_error}")
    
    # Save to cache
    cache[text_hash] = embedding
    _save_embedding_cache(cache)
    
    return embedding


# ============================================================================
# DATABASE AND SEARCH (unchanged from original)
# ============================================================================

DB_PATH = os.environ.get("SEMGREP_DB_PATH", "/workspace/memory/lancedb/semgrep")
TOP_K = 10
BACKEND = os.environ.get("SEMGREP_BACKEND", "auto")  # sqlite | lance | auto

# Threshold: use LanceDB for projects with more files than this
LANCEDB_FILE_THRESHOLD = 100


def _try_import_lancedb():
    """Try to import lancedb, return None if unavailable."""
    try:
        import lancedb
        return lancedb
    except ImportError:
        return None


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _pack_embedding(embedding: List[float]) -> bytes:
    """Pack a float list into bytes for SQLite BLOB storage."""
    return struct.pack(f"{len(embedding)}f", *embedding)


def _unpack_embedding(blob: bytes) -> List[float]:
    """Unpack bytes back into a float list."""
    count = len(blob) // 4
    return list(struct.unpack(f"{count}f", blob))


# ---------------------------------------------------------------------------
# Abstract vector store interface
# ---------------------------------------------------------------------------

class VectorStore(ABC):
    """Abstract interface for vector storage backends."""

    @abstractmethod
    def has_table(self, table_name: str) -> bool: ...

    @abstractmethod
    def create_table(self, table_name: str, records: List[Dict[str, Any]]) -> None: ...

    @abstractmethod
    def drop_table(self, table_name: str) -> None: ...

    @abstractmethod
    def search_table(
        self, table_name: str, query_embedding: List[float], top_k: int
    ) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def list_table_names(self) -> List[str]: ...

    @abstractmethod
    def get_projects(self) -> List[str]: ...


# ---------------------------------------------------------------------------
# SQLite backend
# ---------------------------------------------------------------------------

class SQLiteVectorStore(VectorStore):
    """Vector store backed by SQLite with BLOB embeddings and cosine similarity."""

    def __init__(self, db_path: str):
        self.db_file = Path(db_path) / "semgrep_vectors.db"
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_file))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._init_meta_table()

    # -- schema helpers ------------------------------------------------------

    def _init_meta_table(self):
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS _meta ("
            "  table_name TEXT PRIMARY KEY,"
            "  dim INTEGER NOT NULL"
            ")"
        )
        self.conn.commit()

    def _ensure_table(self, table_name: str, dim: int):
        safe = self._safe_name(table_name)
        self.conn.execute(
            f"CREATE TABLE IF NOT EXISTS {safe} ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  project TEXT NOT NULL,"
            "  file TEXT NOT NULL,"
            "  chunk TEXT NOT NULL,"
            "  embedding BLOB NOT NULL"
            ")"
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO _meta (table_name, dim) VALUES (?, ?)",
            (table_name, dim),
        )
        self.conn.commit()

    @staticmethod
    def _safe_name(name: str) -> str:
        """Sanitize table name for SQL (only allow alphanumerics and underscores)."""
        return "".join(c if c.isalnum() or c == "_" else "_" for c in name)

    # -- VectorStore interface -----------------------------------------------

    def has_table(self, table_name: str) -> bool:
        safe = self._safe_name(table_name)
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (safe,)
        )
        return cur.fetchone() is not None

    def create_table(self, table_name: str, records: List[Dict[str, Any]]) -> None:
        if not records:
            return
        dim = len(records[0]["embedding"])
        self._ensure_table(table_name, dim)

        # Drop old data
        safe = self._safe_name(table_name)
        self.conn.execute(f"DELETE FROM {safe}")

        rows = [
            (r["project"], r["file"], r["chunk"], _pack_embedding(r["embedding"]))
            for r in records
        ]
        self.conn.executemany(
            f"INSERT INTO {safe} (project, file, chunk, embedding) VALUES (?, ?, ?, ?)",
            rows,
        )
        self.conn.commit()

    def drop_table(self, table_name: str) -> None:
        safe = self._safe_name(table_name)
        self.conn.execute(f"DROP TABLE IF EXISTS {safe}")
        self.conn.execute("DELETE FROM _meta WHERE table_name = ?", (table_name,))
        self.conn.commit()

    def search_table(
        self, table_name: str, query_embedding: List[float], top_k: int
    ) -> List[Dict[str, Any]]:
        if not self.has_table(table_name):
            return []

        safe = self._safe_name(table_name)
        cur = self.conn.execute(f"SELECT project, file, chunk, embedding FROM {safe}")
        scored: List[Dict[str, Any]] = []
        for project, file, chunk, blob in cur.fetchall():
            vec = _unpack_embedding(blob)
            sim = _cosine_similarity(query_embedding, vec)
            scored.append(
                {
                    "project": project,
                    "file": file,
                    "chunk": chunk,
                    "score": round(sim, 3),
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def list_table_names(self) -> List[str]:
        cur = self.conn.execute("SELECT table_name FROM _meta")
        return [row[0] for row in cur.fetchall()]

    def get_projects(self) -> List[str]:
        projects: set = set()
        for table_name in self.list_table_names():
            safe = self._safe_name(table_name)
            cur = self.conn.execute(f"SELECT DISTINCT project FROM {safe}")
            for row in cur.fetchall():
                projects.add(row[0])
        return sorted(projects)

    def close(self):
        self.conn.close()


# ---------------------------------------------------------------------------
# LanceDB backend (optional)
# ---------------------------------------------------------------------------

class LanceDBVectorStore(VectorStore):
    """Vector store backed by LanceDB."""

    def __init__(self, db_path: str):
        lancedb = _try_import_lancedb()
        if lancedb is None:
            raise ImportError(
                "lancedb is not installed. Install with: pip install lancedb"
            )
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(self.db_path))

    def has_table(self, table_name: str) -> bool:
        return table_name in self.db.table_names()

    def create_table(self, table_name: str, records: List[Dict[str, Any]]) -> None:
        import pyarrow as pa

        schema = pa.schema(
            [
                ("project", pa.string()),
                ("file", pa.string()),
                ("chunk", pa.string()),
                ("embedding", pa.list_(pa.float32(), 1024)),
            ]
        )

        try:
            self.db.drop_table(table_name)
        except Exception:
            pass
        table = self.db.create_table(table_name, schema=schema)
        table.add(records)

    def drop_table(self, table_name: str) -> None:
        try:
            self.db.drop_table(table_name)
        except Exception:
            pass

    def search_table(
        self, table_name: str, query_embedding: List[float], top_k: int
    ) -> List[Dict[str, Any]]:
        if not self.has_table(table_name):
            return []
        table = self.db.open_table(table_name)
        results = table.search(query_embedding).limit(top_k).to_list()

        scored = []
        for r in results:
            distance = r.get("_distance", 1.0)
            score = 1.0 - distance
            scored.append(
                {
                    "project": r.get("project"),
                    "file": r.get("file"),
                    "chunk": r.get("chunk", "")[:500],
                    "score": round(score, 3),
                }
            )
        return scored

    def list_table_names(self) -> List[str]:
        return [t for t in self.db.table_names() if t.startswith("project_")]

    def get_projects(self) -> List[str]:
        projects: set = set()
        for t in self.list_table_names():
            table = self.db.open_table(t)
            rows = table.to_pandas()
            if not rows.empty and "project" in rows.columns:
                projects.update(rows["project"].unique())
        return sorted(projects)


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

def _select_backend(db_path: str, file_count: int = 0) -> VectorStore:
    """Choose the appropriate backend based on config and availability."""
    lancedb = _try_import_lancedb()
    has_lancedb = lancedb is not None

    # Check for existing LanceDB data (backward compat)
    lancedb_path = Path(db_path)
    has_lancedb_data = lancedb_path.exists() and any(
        f.suffix == ".lance" for f in lancedb_path.rglob("*")
    )

    mode = BACKEND.lower()

    if mode == "sqlite":
        return SQLiteVectorStore(db_path)

    if mode == "lance":
        if not has_lancedb:
            raise ImportError(
                "SEMGREP_BACKEND=lance but lancedb is not installed. "
                "Install with: pip install lancedb"
            )
        return LanceDBVectorStore(db_path)

    # auto mode
    if has_lancedb and (file_count > LANCEDB_FILE_THRESHOLD or has_lancedb_data):
        return LanceDBVectorStore(db_path)

    return SQLiteVectorStore(db_path)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class SemanticGrep:
    def __init__(self, db_path: str = DB_PATH, backend: str = None):
        self.db_path = Path(db_path)
        self._backend_override = backend
        self._store: Optional[VectorStore] = None
        
        # Initialize backend detection
        print(f"\U0001f517 Embedding backend: {EMBED_BACKEND}")
        _detect_available_backends()

    @property
    def store(self) -> VectorStore:
        if self._store is None:
            mode = self._backend_override or BACKEND
            lancedb = _try_import_lancedb()

            # Check for existing LanceDB data
            has_lancedb_data = self.db_path.exists() and any(
                f.suffix == ".lance" for f in self.db_path.rglob("*")
            )

            if mode == "sqlite":
                self._store = SQLiteVectorStore(str(self.db_path))
            elif mode == "lance":
                if lancedb is None:
                    raise ImportError(
                        "SEMGREP_BACKEND=lance but lancedb is not installed."
                    )
                self._store = LanceDBVectorStore(str(self.db_path))
            else:
                # auto: prefer LanceDB if existing data found or available
                if lancedb is not None and has_lancedb_data:
                    self._store = LanceDBVectorStore(str(self.db_path))
                elif lancedb is not None:
                    self._store = LanceDBVectorStore(str(self.db_path))
                else:
                    self._store = SQLiteVectorStore(str(self.db_path))
        return self._store

    def get_embedding(self, text: str) -> List[float]:
        """Get embedding using the configured backend priority order."""
        return get_embedding(text)

    def index_project(self, project_path: str, ignore_patterns: List[str] = None):
        """Index all code files in a project."""
        project_path = Path(project_path).resolve()
        project_name = project_path.name
        table_name = f"project_{hashlib.md5(project_name.encode()).hexdigest()[:8]}"

        print(f"\U0001f4c2 Indexing {project_name}...")

        # Collect files
        files = self._collect_files(project_path, ignore_patterns or [])
        print(f"   Found {len(files)} files to index")

        # Auto-select backend based on file count
        if self._backend_override is None and BACKEND == "auto":
            lancedb = _try_import_lancedb()
            if lancedb is None or len(files) <= LANCEDB_FILE_THRESHOLD:
                self._store = SQLiteVectorStore(str(self.db_path))
            else:
                self._store = LanceDBVectorStore(str(self.db_path))
            print(f"   Using backend: {type(self._store).__name__}")

        # Embed and store
        records = []
        for i, file_path in enumerate(files):
            try:
                content = file_path.read_text(errors="ignore")
                if len(content) > 10000:
                    content = content[:10000]
                chunks = self._chunk_file(content, file_path.suffix)

                for chunk in chunks:
                    try:
                        embedding = self.get_embedding(chunk)
                        records.append(
                            {
                                "project": project_name,
                                "file": str(file_path.relative_to(project_path)),
                                "chunk": chunk,
                                "embedding": embedding,
                            }
                        )
                    except Exception as e:
                        if "500" in str(e):
                            continue
                        print(
                            f"   \u26a0\ufe0f Embedding failed for chunk in {file_path}: {e}"
                        )
                        continue

                if (i + 1) % 10 == 0:
                    print(f"   Processed {i + 1}/{len(files)} files...")
            except Exception as e:
                print(f"   \u26a0\ufe0f Skipped {file_path}: {e}")

        if records:
            self.store.create_table(table_name, records)
            print(f"\u2705 Indexed {len(records)} chunks from {len(files)} files")
        else:
            print("\u26a0\ufe0f No files indexed")

    def search(self, query: str, project: str = None, top_k: int = TOP_K) -> List[Dict]:
        """Semantic search using vector similarity."""
        print(f"\U0001f50d Searching: {query}")

        query_embedding = self.get_embedding(query)

        all_results = []
        table_names = self.store.list_table_names()

        if project:
            project_name = Path(project).name if Path(project).exists() else project
            table_name = f"project_{hashlib.md5(project_name.encode()).hexdigest()[:8]}"
            if table_name not in table_names:
                print(
                    f"   \u26a0\ufe0f Project '{project_name}' not indexed. Available: {self.list_projects()}"
                )
                return []
            table_names = [table_name]
            print(f"   \U0001f50d Searching in project: {project_name}")

        for table_name in table_names:
            results = self.store.search_table(table_name, query_embedding, top_k)
            for r in results:
                if project and r.get("project") != project_name:
                    continue
                all_results.append(
                    {
                        "file": r.get("file"),
                        "chunk": r.get("chunk")[:500],
                        "score": r.get("score", 0),
                    }
                )

        all_results.sort(key=lambda x: x["score"] if x["score"] else 0, reverse=True)
        return all_results[:top_k]

    def list_projects(self) -> List[str]:
        """List indexed projects."""
        return self.store.get_projects()

    def _collect_files(self, path: Path, ignore_patterns: List[str]) -> List[Path]:
        """Collect code files from path."""
        extensions = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".go",
            ".rs",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".cs",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".scala",
            ".vue",
            ".svelte",
            ".md",
            ".json",
            ".yaml",
            ".yml",
        }

        default_ignores = {
            "node_modules",
            ".git",
            "__pycache__",
            "dist",
            "build",
            ".next",
        }

        files = []
        gitignore = path / ".gitignore"
        ignore_set = set()
        if gitignore.exists():
            for line in gitignore.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    ignore_set.add(line)

        for f in path.rglob("*"):
            if not f.is_file():
                continue

            rel = f.relative_to(path)
            rel_str = str(rel)

            if any(p in rel_str for p in default_ignores):
                continue

            skip = False
            for pattern in ignore_set:
                if pattern in rel_str or f.name == pattern:
                    skip = True
                    break
            if skip:
                continue

            if f.suffix in extensions:
                files.append(f)

        return files

    def _chunk_file(self, content: str, ext: str) -> List[str]:
        """Simple chunking by lines."""
        lines = content.split("\n")
        chunks = []

        chunk_size = 50
        overlap = 5

        for i in range(0, len(lines), chunk_size - overlap):
            chunk = "\n".join(lines[i : i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
            if len(chunks) >= 20:
                break

        return chunks or [content[:2000]]


def main():
    parser = argparse.ArgumentParser(description="Local semantic grep")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # index command
    index_parser = subparsers.add_parser("index", help="Index a project")
    index_parser.add_argument("path", help="Project path to index")

    # search command
    search_parser = subparsers.add_parser("search", help="Search indexed code")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--project", "-p", help="Project to search")
    search_parser.add_argument("-e", "--exact", help="Fallback to ripgrep")
    search_parser.add_argument(
        "-c", "--context", type=int, default=3, help="Context lines"
    )

    # list command
    subparsers.add_parser("ls", help="List indexed projects")

    args = parser.parse_args()

    sg = SemanticGrep()

    if args.command == "index":
        sg.index_project(args.path)

    elif args.command == "search":
        if args.exact:
            import subprocess

            result = subprocess.run(
                ["rg", "-n", f"-C{args.context}", args.exact],
                capture_output=True,
                text=True,
            )
            print(result.stdout or "No matches found")
        else:
            results = sg.search(args.query, args.project)
            if results:
                for r in results:
                    print(f"\n\U0001f4c4 {r['file']} (score: {r['score']:.3f})")
                    print(f"   {r['chunk'][:300]}...")
            else:
                print("No results found")

    elif args.command == "ls":
        projects = sg.list_projects()
        if projects:
            for p in projects:
                print(f"  {p}")
        else:
            print("No indexed projects")


if __name__ == "__main__":
    main()

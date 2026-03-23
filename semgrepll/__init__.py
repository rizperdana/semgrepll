#!/usr/bin/env python3
"""
Semgrep - Local Semantic Code Search
Uses Ollama embeddings + LanceDB for offline semantic search.
"""

import os
import sys
import json
import argparse
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
import lancedb
import requests

# Config
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/embeddings")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "mxbai-embed-large")
DB_PATH = os.environ.get("SEMGREP_DB_PATH", "/workspace/memory/lancedb/semgrep")
TOP_K = 10


class SemanticGrep:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(self.db_path))

    def get_embedding(self, text: str) -> List[float]:
        """Get embedding from Ollama."""
        resp = requests.post(
            OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=60
        )
        resp.raise_for_status()
        return resp.json()["embedding"]

    def index_project(self, project_path: str, ignore_patterns: List[str] = None):
        """Index all code files in a project."""
        project_path = Path(project_path).resolve()
        project_name = project_path.name
        table_name = f"project_{hashlib.md5(project_name.encode()).hexdigest()[:8]}"

        print(f"📂 Indexing {project_name}...")

        # Collect files
        files = self._collect_files(project_path, ignore_patterns or [])
        print(f"   Found {len(files)} files to index")

        # Embed and store
        records = []
        for i, file_path in enumerate(files):
            try:
                content = file_path.read_text(errors="ignore")
                if len(content) > 10000:
                    content = content[:10000]  # Truncate large files
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
                            continue  # Skip failed chunks
                        print(f"   ⚠️ Embedding failed for chunk in {file_path}: {e}")
                        continue

                if (i + 1) % 10 == 0:
                    print(f"   Processed {i + 1}/{len(files)} files...")
            except Exception as e:
                print(f"   ⚠️ Skipped {file_path}: {e}")

        if records:
            # Use pyarrow for schema
            import pyarrow as pa

            schema = pa.schema(
                [
                    ("project", pa.string()),
                    ("file", pa.string()),
                    ("chunk", pa.string()),
                    ("embedding", pa.list_(pa.float32(), 1024)),
                ]
            )

            # Drop existing table if any, then create
            try:
                self.db.drop_table(table_name)
            except:
                pass
            table = self.db.create_table(table_name, schema=schema)
            table.add(records)
            print(f"✅ Indexed {len(records)} chunks from {len(files)} files")
        else:
            print("⚠️ No files indexed")

    def search(self, query: str, project: str = None, top_k: int = TOP_K) -> List[Dict]:
        """Semantic search using vector similarity."""
        print(f"🔍 Searching: {query}")

        # Get query embedding
        query_embedding = self.get_embedding(query)

        # Determine which tables to search
        all_results = []
        tables_resp = self.db.list_tables()
        table_names = [t for t in tables_resp.tables if t.startswith("project_")]

        if project:
            # Extract project name from path if full path given
            project_name = Path(project).name if Path(project).exists() else project
            # Compute the correct table hash
            table_name = f"project_{hashlib.md5(project_name.encode()).hexdigest()[:8]}"
            if table_name not in table_names:
                print(
                    f"   ⚠️ Project '{project_name}' not indexed. Available: {self.list_projects()}"
                )
                return []
            table_names = [table_name]
            print(f"   🔍 Searching in project: {project_name}")

        for table_name in table_names:
            table = self.db.open_table(table_name)
            results = table.search(query_embedding).limit(top_k).to_list()

            for r in results:
                if project and r.get("project") != project_name:
                    continue
                # LanceDB returns _distance, convert to similarity score
                distance = r.get("_distance", 1.0)
                score = 1.0 - distance  # Convert distance to similarity
                all_results.append(
                    {
                        "file": r.get("file"),
                        "chunk": r.get("chunk")[:500],
                        "score": round(score, 3),
                    }
                )

        # Sort by score and return top_k
        all_results.sort(key=lambda x: x["score"] if x["score"] else 0, reverse=True)
        return all_results[:top_k]

    def list_projects(self) -> List[str]:
        """List indexed projects."""
        tables_resp = self.db.list_tables()
        projects = set()
        for t in tables_resp.tables:
            if t.startswith("project_"):
                table = self.db.open_table(t)
                rows = table.to_pandas()
                if not rows.empty and "project" in rows.columns:
                    projects.update(rows["project"].unique())
        return sorted(projects)

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

        # Default ignore dirs
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

            # Check default ignores
            if any(p in rel_str for p in default_ignores):
                continue

            # Check gitignore patterns
            skip = False
            for pattern in ignore_set:
                if pattern in rel_str or f.name == pattern:
                    skip = True
                    break
            if skip:
                continue

            # Check extension
            if f.suffix in extensions:
                files.append(f)

        return files

    def _chunk_file(self, content: str, ext: str) -> List[str]:
        """Simple chunking by lines."""
        lines = content.split("\n")
        chunks = []

        # Split into overlapping chunks of ~50 lines
        chunk_size = 50
        overlap = 5

        for i in range(0, len(lines), chunk_size - overlap):
            chunk = "\n".join(lines[i : i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
            if len(chunks) >= 20:  # Limit chunks per file
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
            # Fallback to ripgrep
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
                    print(f"\n📄 {r['file']} (score: {r['score']:.3f})")
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

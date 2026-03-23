# semgrepll

> **Local semantic code search for AI agents and developers**
> 
> Search your codebase using natural language — no API keys, no cloud, 100% offline.

[![PyPI Version](https://img.shields.io/pypi/v/semgrepll)](https://pypi.org/project/semgrepll/)
[![License: MIT](https://img.shields.io/pypi/l/semgrepll)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/semgrepll)](https://pypi.org/project/semgrepll/)

## What is semgrepll?

**semgrepll** (pronounced "sem-grep-ell") is a local semantic code search tool that lets you search your codebase using natural language queries. Unlike traditional grep that searches for exact text matches, semgrepll understands *meaning* — so you can ask questions like:

- "Where is authentication configured?"
- "How does the user login flow work?"
- "Find the payment processing logic"

## Why semgrepll?

### For Developers
- **Offline & Private** — Your code never leaves your machine
- **No API Keys** — Works without OpenAI, Anthropic, or any cloud service
- **Fast** — Local Ollama embeddings, SQLite/LanceDB storage
- **Universal** — Works with any programming language

### For AI Agents
- **Understand Codebases** — Semantic search helps agents navigate unfamiliar code
- **Reduce Token Usage** — Instead of reading entire files, find exact locations
- **Faster Context** — Get relevant code sections in milliseconds

### Comparison

| Tool | Type | Requires API | Offline | Best For |
|------|------|--------------|---------|----------|
| **semgrepll** | Semantic | ❌ No | ✅ Yes | Local AI dev |
| GitHub Copilot | Semantic | ✅ Yes | ❌ No | Cloud IDEs |
| ripgrep (rg) | Exact | ❌ No | ✅ Yes | Known patterns |
| Sourcegraph | Semantic | ✅ Yes | ❌ No | Enterprise |

## Installation

```bash
# Basic (SQLite backend - works out of the box)
pip install semgrepll

# With LanceDB (recommended for large projects)
pip install semgrepll[lance]
```

### Requirements

- **Python** 3.10+
- **Ollama** running locally with `mxbai-embed-large` model

```bash
# Install Ollama and the embedding model
ollama pull mxbai-embed-large
```

## Quick Start

```bash
# 1. Index your project (one-time)
semgrep index /path/to/your/project

# 2. Search semantically
semgrep search "how does authentication work"

# 3. List indexed projects
semgrep ls

# 4. Remove a project
semgrep rm project-name
```

## Usage

### CLI Commands

```bash
semgrep index <path>           # Index a project for search
semgrep search <query>         # Search indexed code
semgrep ls                     # List all indexed projects
semgrep rm <project>           # Remove a project index
```

### Options

```bash
semgrep search "query"         # Search all indexed projects
semgrep search "query" -p myproject  # Search specific project
semgrep search "query" -e "pattern"  # Fallback to ripgrep
```

## Configuration

### Environment Variables

```bash
# Ollama endpoint (default: http://127.0.0.1:11434)
export OLLAMA_URL="http://localhost:11434/api/embeddings"

# Embedding model (default: mxbai-embed-large)
export EMBED_MODEL="mxbai-embed-large"

# Storage backend (auto | sqlite | lance)
# - auto: SQLite for small projects, LanceDB for large
# - sqlite: Force SQLite (no extra deps)
# - lance: Force LanceDB (needs lancedb installed)
export SEMGREP_BACKEND=auto

# Database path (default: ~/.semgrepll/db)
export SEMGREP_DB_PATH="/path/to/db"
```

### When to Use Which Backend

| Project Size | Recommended Backend | Why |
|--------------|---------------------|-----|
| Small (< 100 files) | SQLite | Zero deps, fast enough |
| Large (100+ files) | LanceDB | Better vector indexing |
| Mixed | auto | Automatic selection |

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Your      │────▶│   semgrepll   │────▶│   Ollama    │
│   Query     │     │  (embed)      │     │ (mxbai)     │
└─────────────┘     └──────────────┘     └─────────────┘
                                                  │
                     ┌──────────────┐            │
                     │   SQLite or   │◀───────────┘
                     │   LanceDB     │
                     │  (similarity) │
                     └──────────────┘
```

1. **Index** — Your code files are chunked and embedded using Ollama
2. **Search** — Your query is embedded, then compared against indexed code
3. **Results** — Most similar code sections returned with relevance scores

## Use Cases

### Developer Onboarding
```bash
# New to the codebase? Ask questions!
semgrep search "how do I add a new API route"
semgrep search "where is error handling"
```

### AI Agent Integration
```python
# In your AI agent
subprocess.run(["semgrep", "search", "-p", "myproject", "auth configuration"])
# Returns: file paths + code snippets + relevance scores
```

### Code Review
```bash
# Find all places that touch payments
semgrep search "payment processing"
```

## Example Output

```
🔍 Searching: how does authentication work

📄 auth.ts (score: 0.85)
   // Authentication module
   export class AuthService {
     async signIn(email: string, password: string) {
       return this.client.auth.signInWithPassword({...});
     }
   }

📄 middleware.ts (score: 0.72)
   export function authMiddleware(request: NextRequest) {
     const token = request.headers.get('authorization');
     ...
   }
```

## Contributing

```bash
# Clone and develop
git clone https://github.com/rizperdana/semgrepll
cd semgrepll
pip install -e ".[all]"
pip install pytest black mypy

# Run tests
pytest

# Format
black semgrepll/
```

## License

MIT License — see [LICENSE](LICENSE) for details.

## Related

- [Ollama](https://ollama.ai/) — Run LLMs locally
- [LanceDB](https://lancedb.com/) — Vector database
- [ripgrep](https://github.com/BurntSushi/ripgrep) — Fast line-oriented search

---

**TL;DR**: `pip install semgrepll` → `semgrep index ./src` → `semgrep search "how does X work"`

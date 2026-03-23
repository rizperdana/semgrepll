# semgrepll

Local semantic code search using Ollama embeddings + LanceDB.

## Installation

```bash
pip install semgrepll
```

## Requirements

- **Ollama** running with `mxbai-embed-large` model at `http://127.0.0.1:11434`
- **LanceDB** for vector storage (installed automatically)

## Quick Start

```bash
# Index a project (run once)
semgrep index /path/to/project

# Search semantically
semgrep search "how does authentication work"

# List indexed projects
semgrep ls

# Remove a project
semgrep rm project-name
```

## Usage

```
semgrep [command] [options]

Commands:
  index <path>    Index a project for semantic search
  search <query>  Search indexed code semantically
  ls              List indexed projects
  rm <project>    Remove a project index

Options:
  -p, --project PROJECT  Filter to specific project
  -e, --exact PATTERN   Fallback to ripgrep
  -c, --context N       Context lines for exact search
  -h, --help            Show help
```

## Configuration

```bash
# Default Ollama URL (can override)
export OLLAMA_URL="http://127.0.0.1:11434/api/embeddings"

# Default embed model
export EMBED_MODEL="mxbai-embed-large"

# Database path
export SEMGREP_DB_PATH="/path/to/db"
```

## When to Use

| Scenario | Tool |
|----------|------|
| Small codebase (<20 files) | Use `rg` directly |
| Large codebase, know pattern | Use `rg` |
| Exploratory search | semgrepll |
| Natural language query | semgrepll |

## License

MIT

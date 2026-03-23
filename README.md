# semgrepll — Local Semantic Code Search

<p align="center">
  <img src="semgrepll-demo.jpg" alt="semgrepll - Local Semantic Code Search for AI Agents" width="800">
</p>

<p align="center">
  <a href="https://pypi.org/project/semgrepll/">
    <img src="https://img.shields.io/pypi/v/semgrepll?color=3FB950" alt="PyPI v1.3.1">
  </a>
  <a href="https://github.com/rizperdana/semgrepll/blob/master/LICENSE">
    <img src="https://img.shields.io/pypi/l/semgrepll?color=3FB950" alt="MIT License">
  </a>
  <a href="https://github.com/rizperdana/semgrepll">
    <img src="https://img.shields.io/github/stars/rizperdana/semgrepll?color=3FB950" alt="GitHub stars">
  </a>
  <a href="https://rizperdana.github.io/semgrepll">
    <img src="https://img.shields.io/badge/demo-github pages-3FB950" alt="GitHub Pages">
  </a>
</p>

100% offline semantic code search for AI coding agents. Find code by meaning, not just keywords.

## What is semgrepll?

semgrepll is a local semantic grep tool that uses embeddings to search your codebase by meaning. Runs entirely offline — no external APIs, no rate limits, your code never leaves your machine.

## Features

- **Multi-backend**: llama.cpp → ONNX → Ollama (auto-detects fastest)
- **100% offline**: No external API calls, works without internet
- **Hybrid storage**: SQLite for small projects, LanceDB for large codebases
- **Embedding caching**: Fast re-indexing with cached embeddings
- **Semantic search**: Find code by meaning, not just keywords

## Installation

```bash
pip install semgrepll
```

## Quick Start

```bash
# Index a project for semantic search
semgrep index ./my-project

# Search semantically - find code by meaning
semgrep search "authentication logic"

# List all indexed projects
semgrep ls
```

## Why Offline?

- **Privacy**: Your code never leaves your machine
- **No rate limits**: Unlimited searches
- **No API keys**: No external dependencies
- **Air-gapped environments**: Works completely offline

## Backends

| Rank | Backend | Speed | Notes |
|------|---------|-------|-------|
| 1 | llama.cpp | ~1s | Fastest - requires GGUF model |
| 2 | ONNX | ~3s | Local - uses HuggingFace model |
| 3 | Ollama | ~6s | Local server fallback |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBED_BACKEND` | auto | Backend: llama, onnx, ollama |
| `LLM_MODEL_PATH` | - | Path to GGUF model (llama.cpp) |
| `ONNX_MODEL_PATH` | auto | Path to ONNX model |
| `SEMGREP_BACKEND` | auto | Storage: sqlite, lance |

## For AI Agents

Install as a skill for Claude Code, Cursor, OpenCode, and more:

```bash
pip install semgrepll
```

See [semgrepll-skill](https://github.com/rizperdana/semgrepll-skill) for agent-specific configurations.

## Use Cases

- **Find related code**: Search for "payment" finds payment processing, Stripe integration, PayPal, etc.
- **Semantic search**: "authentication" finds JWT, OAuth, sessions, login, bcrypt
- **Code discovery**: Understand large codebases without reading every file
- **AI agent tool**: Give your AI coding assistant semantic search capabilities

## License

MIT — see [LICENSE](LICENSE)

---

<p align="center">
  <a href="https://pypi.org/project/semgrepll/">PyPI</a> • 
  <a href="https://github.com/rizperdana/semgrepll">GitHub</a> • 
  <a href="https://rizperdana.github.io/semgrepll">Demo</a>
</p>

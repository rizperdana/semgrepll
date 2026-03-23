# semgrepll - Local Semantic Code Search

Local semantic grep using multiple embedding backends - 100% offline capable.

## Features

- **Multi-backend support**: llama.cpp, ONNX, Ollama
- **Auto-detection**: Automatically picks fastest available local backend
- **Hybrid storage**: SQLite (small projects) or LanceDB (large)
- **100% offline**: No external connections
- **Embedding caching**: Fast re-indexing

## Backends (priority order)

1. **llama.cpp** - Fastest local (requires llama-cpp-python + GGUF model)
2. **ONNX** - Local runtime using HuggingFace model files (~3s)
3. **Ollama** - Local server fallback (~6s)

## Installation

```bash
pip install semgrepll
pip install semgrepll[onnx]  # for ONNX backend
```

## Usage

```bash
# Index a project (auto-detects backend)
semgrep index /path/to/project

# Search
semgrep search "authentication logic"

# List indexed projects
semgrep ls
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `EMBED_BACKEND` | Backend: auto, llama, onnx, ollama | auto |
| `EMBED_MODEL` | Model name | mxbai-embed-large-v1 |
| `LLM_MODEL_PATH` | Path to GGUF model (for llama.cpp) | - |
| `ONNX_MODEL_PATH` | Path to ONNX model | auto-detect |
| `SEMGREP_BACKEND` | Storage: auto, sqlite, lance | auto |

## Benchmark

| Backend | Speed |
|---------|-------|
| llama.cpp | ~1s (theoretical) |
| ONNX | ~3s |
| Ollama | ~6s |

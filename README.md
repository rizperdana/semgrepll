# semgrepll - Local Semantic Code Search

Local semantic grep using multiple embedding backends with auto-detection.

## Features

- **Multi-backend support**: llama.cpp, HuggingFace API, ONNX, Ollama
- **Auto-detection**: Automatically picks fastest available backend
- **Hybrid storage**: SQLite (small projects) or LanceDB (large)
- **Offline capable**: Works without network using ONNX or Ollama
- **Embedding caching**: Fast re-indexing

## Backends (priority order)

1. **llama.cpp** - Fastest local (requires llama-cpp-python)
2. **HuggingFace API** - Fastest overall (requires network + token)
3. **ONNX** - Fast local offline (~3s)
4. **Ollama** - Fallback (~6s)

## Installation

```bash
pip install semgrepll
pip install semgrepll[all]  # includes lance, onnx
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
| `EMBED_BACKEND` | Backend: auto, llama, hf, onnx, ollama | auto |
| `EMBED_MODEL` | Model name | mxbai-embed-large-v1 |
| `HF_TOKEN` | HuggingFace token (for HF API) | - |
| `LLM_MODEL_PATH` | Path to GGUF model (for llama.cpp) | - |
| `ONNX_MODEL_PATH` | Path to ONNX model | auto-detect |
| `SEMGREP_BACKEND` | Storage: auto, sqlite, lance | auto |

## Benchmark

| Backend | Speed |
|---------|-------|
| HF API | ~0.5s |
| ONNX | ~3s |
| Ollama | ~6s |

# pycognita

Cognita™ is a lightweight framework designed for flexible file tooling using GStreamer-inspired pipelines. By chaining processing steps, Cognita™ allows for robust file analysis and manipulation. The project combines traditional deterministic methods with modern AI capabilities to handle data more intelligently.

Lightweight, GStreamer-inspired pipelines for file tooling. The initial tool is a `TypeFinder` that inspects a file header and, if needed, asks an Ollama model to guess the type and MIME.

## Structure
- `cognita/`: Cognita™ library code (e.g., `cognita.pipeline`, `cognita.type_finder`, `cognita.ollama`, `cognita.caps`).
- `tools/`: CLI tools (e.g., `cognita_tools.typefinder`).
- `requirements-dev.txt`, `pyproject.toml` at repo root.

## Usage
```bash
python -m pip install -e .
typefinder path/to/file.ext
```

Flags:
- `--no-ollama` to disable the AI fallback.
- `--ollama-model` and `--ollama-url` to point at your Ollama instance (defaults: `llama3.1`, `http://localhost:11434`).

## Notes
- Header detection covers common formats (PNG, JPEG, GIF, PDF, ZIP/OOXML, ELF, MP3, WAV, MP4). Unknown types rely on the model.
- Ollama is queried with a JSON-only prompt; errors are surfaced rather than silently ignored.
- CAPS can be serialized to Turtle with `cognita.caps.caps_to_turtle(caps)` for ontology-style integration (includes `rdfs:subClassOf` relations).

## Licensing
- Dual-licensed: GPL-3.0-only (see `LICENSE`) or a commercial license (see `LICENSE-COMMERCIAL.md`).
- Contributors must agree to the CLA (`CLA.md`) so contributions can be used under both licenses.

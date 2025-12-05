# PyCognita

![CI](https://github.com/gazgiz/pycognita/actions/workflows/ci.yml/badge.svg)

**Cognita™** is a lightweight, pipeline-based framework for intelligent file analysis and narration. Inspired by GStreamer, it allows you to chain processing steps to inspect, filter, and describe data using both deterministic methods and modern AI capabilities.

## Key Features

- **Pipeline Architecture**: Flexible, chainable elements (Source -> Filter -> Sink) for processing data streams.
- **Hybrid Type Detection**: Robust file type detection using header heuristics (including mbox, EML, PDF, images) with an AI fallback (Ollama) for unknown types.
- **AI-Powered Narration**:
    - **ImageNarrator**: Uses Vision LLMs (via Ollama) to generate detailed descriptions of images.
    - **MailboxNarrator**: Parses and summarizes email archives (mbox/EML) into readable text.
- **Extensible**: Easy to create new `Narrator` subclasses for custom content types.

## Structure

- `cognita/`: Core library code.
    - `pipeline.py`: Pipeline orchestration.
    - `source.py`: Data sources (`DiscreteDataSource`, `TimeSeriesDataSource`).
    - `narrator.py`: Base class for content describers.
    - `type_finder.py`: Heuristic and AI-based type detection.
- `tools/`: CLI tools.
    - `imagenarrator.py`: CLI for describing images.

## Usage

### Installation
```bash
python -m pip install -e .
```

### Image Narration CLI
Describe an image using a local Ollama model:
```bash
python -m tools.imagenarrator path/to/image.jpg --ollama-model qwen2.5vl:3b
```

### Library Example
```python
from cognita import Pipeline, DiscreteDataSource, ImageNarrator, SilentSink

pipeline = Pipeline([
    DiscreteDataSource("path/to/image.jpg"),
    ImageNarrator(),  # Uses default Ollama model
    SilentSink()      # Prints output
])
pipeline.run()
```

## Community & Legal

- **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and guidelines.
- **Code of Conduct**: We follow the Contributor Covenant (see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)).
- **Security**: Report vulnerabilities to `inquiry@cleverplant.com` (see [SECURITY.md](SECURITY.md)).
- **Licensing**: Dual-licensed under GPL-3.0-only (`LICENSE`) or Commercial (`LICENSE-COMMERCIAL.md`). Contributors must sign the [CLA](https://cla-assistant.io/gazgiz/pycognita).
  [![CLA assistant](https://cla-assistant.io/readme/badge/gazgiz/pycognita)](https://cla-assistant.io/gazgiz/pycognita)


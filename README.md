# PyCognita

![CI](https://github.com/gazgiz/pycognita/actions/workflows/ci.yml/badge.svg)
[![codecov](https://codecov.io/gh/gazgiz/pycognita/graph/badge.svg?token=CODECOV_TOKEN)](https://codecov.io/gh/gazgiz/pycognita)
[![CLA assistant](https://cla-assistant.io/readme/badge/gazgiz/pycognita)](https://cla-assistant.io/gazgiz/pycognita)


**Cognita™** is a lightweight, pipeline-based framework for intelligent file analysis and narration. Inspired by GStreamer, it allows you to chain processing steps to inspect, filter, and describe data using both deterministic methods and modern AI capabilities.

## Key Features

- **Pipeline Architecture**: Flexible, chainable elements (Source -> Filter -> Sink) for processing data streams.
- **Hybrid Type Detection**: Robust file type detection using header heuristics (including mbox, EML, PDF, images) with an AI fallback (Ollama) for unknown types.
- **AI-Powered Narration**:
    - **ImageNarrator**: Uses Vision LLMs (via Ollama) to generate detailed descriptions of images.
    - **MailboxNarrator**: Parses and summarizes email archives (mbox/EML) into readable text.
- **Identity Aware**:
    - **Automatic Fingerprinting**: Computes SHA-256 hashes for files to ensure stable identification.
    - **Message-ID Extraction**: Native support for extracting Message-IDs from email files (eml/mbox), preserving their identity.
- **RDF-Native Metadata**: Internally treats content metadata as an RDF Graph (using `rdflib`), enabling rich semantic negotiation and compatibility with standard ontologies (`schema.org`, `dcterms`).
- **Knowledge Graph Extraction**:
    - **TripleExtractor**: Extracts Subject-Predicate-Object (SPO) triples from text into Turtle (TTL) format.
    - **Stable IRIs**: Automatically generates stable Subject IRIs (`urn:cognita:content:<hash>` or `urn:cognita:mail:<id>`) based on content identity.
- **Extensible**: Easy to create new `Narrator` subclasses for custom content types.

## Structure

- `cognita/`: Core library code.
    - `pipeline.py`: Pipeline orchestration.
    - `source.py`: Data sources (`DiscreteDataSource`, `TimeSeriesDataSource`).
    - `caps.py`: RDF-native metadata container (`Caps`).
    - `narrator.py`: Base class for content describers.
    - `mailbox_narrator.py`: Parses and summarizes email content.
    - `mbox_parser.py`: Parses Mbox files into individual messages.
    - `triple_extractor.py`: Extracts RDF triples from text.
    - `type_finder.py`: Heuristic and AI-based type detection.
- `tools/`: CLI tools.
    - `imagenarrator.py`: CLI for describing images.
    - `image2spo.py`: CLI for converting images to Knowledge Graph triples.
    - `mbox2spo.py`: CLI for converting emails to Knowledge Graph triples.

## Usage

### Installation
```bash
python -m pip install -e .
```

```bash
python -m tools.imagenarrator path/to/image.jpg --ollama-model qwen2.5vl:3b
```

### Knowledge Graph Extraction (Image)
Extract SPO triples from an image (Image -> Description -> Triples):
```bash
image2spo path/to/image.jpg \
  --ollama-vision-capable-model qwen2.5vl:3b \
  --ollama-model mistral \
  --tbox path/to/ontology.ttl
```

### Knowledge Graph Extraction (Email)
Extract SPO triples from an Mbox or EML file (Mbox -> Messages -> TripleExtractor):
```bash
mbox2spo path/to/archive.mbox --ollama-model qwen2.5:3b
```
- **Caps-Aware**: Automatically switches prompting strategy to focus on email metadata (Sender, Recipient, Date) and avoid visual hallucinations.
- **Identity Preserved**: Uses the email's Message-ID as a stable Subject IRI in the output graph.

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

# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial
"""
CLI tool for extracting SPO triples from images.

Pipeline:
1. DiscreteDataSource (Image URI)
2. ImageNarrator (Image -> Text Description)
3. TripleExtractor (Text Description -> RDF Triples)
4. SilentSink (Output Triples)
"""

from __future__ import annotations

import argparse
import sys

from cognita.image_narrator import ImageNarrator
from cognita.ollama import OllamaClient
from cognita.pipeline import Pipeline
from cognita.sink import SilentSink
from cognita.source import DiscreteDataSource
from cognita.triple_extractor import TripleExtractor
from cognita.type_finder import TypeFinderError


def build_pipeline(args: argparse.Namespace) -> Pipeline:
    """Construct the processing pipeline based on CLI arguments."""

    # 1. Image Narrator Client
    narrator_client = OllamaClient(
        model=args.ollama_vision_capable_model,
        base_url=args.ollama_url,
        timeout=args.ollama_timeout,
    )

    # 2. Triple Extractor Client
    extractor_client = OllamaClient(
        model=args.ollama_model,
        base_url=args.ollama_url,
        timeout=args.ollama_timeout,
    )

    # 3. Load TBox if provided
    tbox_content = None
    if args.tbox:
        try:
            with open(args.tbox, encoding="utf-8") as f:
                tbox_content = f.read()
        except Exception as e:
            print(f"[warning] Could not read TBox file: {e}", file=sys.stderr)

    # Build pipeline components
    source = DiscreteDataSource(args.uri)
    narrator = ImageNarrator(ollama_client=narrator_client)
    extractor = TripleExtractor(ollama_client=extractor_client, tbox_template=tbox_content)
    sink = SilentSink()

    return Pipeline([source, narrator, extractor, sink])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract SPO triples from an image.")
    parser.add_argument("uri", help="URI of the image to process")

    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
        help="Base URL for Ollama API",
    )

    parser.add_argument(
        "--ollama-vision-capable-model",
        default="llava",
        help="Ollama model for image description (e.g. llava, qwen2.5vl)",
    )

    parser.add_argument(
        "--ollama-model",
        default="mistral",
        help="Ollama model for triple extraction (e.g. mistral, llama3)",
    )

    parser.add_argument(
        "--ollama-timeout",
        type=int,
        default=60,
        help="Timeout for Ollama requests in seconds",
    )

    parser.add_argument(
        "--tbox",
        help="Path to TBox/Ontology file to guide extraction",
    )

    args = parser.parse_args(argv)

    try:
        pipeline = build_pipeline(args)
        sink_output = pipeline.run()
    except (TypeFinderError, FileNotFoundError) as error:
        print(f"[error] {error}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[error] Pipeline failed: {e}", file=sys.stderr)
        return 1

    if sink_output:
        print(sink_output)
    else:
        # If upstream failed silently or produced nothing
        print("[info] No output produced (check models or input)", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

"""# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial"""
from __future__ import annotations

"""
CLI tool for running the ImageNarrator pipeline.

This script demonstrates how to construct and run a pipeline that:
1. Takes a URI (file path or URL) as input.
2. Uses DiscreteDataSource to pass the URI downstream.
3. Uses ImageNarrator to describe the image at that URI (using Ollama).
4. Uses SilentSink to capture and display the output.

Usage:
    python -m tools.imagenarrator <uri> [--ollama-url URL] [--ollama-model MODEL]
"""

import argparse
import sys

from cognita.image_narrator import ImageNarrator
from cognita.ollama import OllamaClient
from cognita.pipeline import Pipeline
from cognita.sink import SilentSink
from cognita.source import DiscreteDataSource
from cognita.type_finder import TypeFinderError


def build_pipeline(args: argparse.Namespace) -> Pipeline:
    """Construct the processing pipeline based on CLI arguments."""
    
    # Configure the Ollama client for image description
    ollama_client = OllamaClient(
        model=args.ollama_model,
        base_url=args.ollama_url,
        timeout=args.ollama_timeout,
    )
    
    # Build the pipeline:
    # Source (URI) -> Narrator (Description) -> Sink (Output)
    return Pipeline(
        [
            # DiscreteDataSource simply emits the URI.
            DiscreteDataSource(args.uri),
            # ImageNarrator reads the URI, checks if it's an image, and describes it.
            ImageNarrator(ollama_client=ollama_client),
            # SilentSink receives the description and prints it (or stores it).
            SilentSink(),
        ]
    )


def main(argv: list[str] | None = None) -> int:
    """
    Main entry point for the CLI tool.
    Parses arguments, builds the pipeline, and runs it.
    """
    parser = argparse.ArgumentParser(description="Run ImageNarrator on a URI.")
    parser.add_argument("uri", help="URI of the image to describe (file://... or http://...)")
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
        help="Base URL for Ollama API",
    )
    parser.add_argument(
        "--ollama-model",
        default="qwen2.5vl", # Original default was "qwen2.5vl", new was "qwen2.5vl:3b". Sticking to original for consistency.
        help="Ollama model to use for vision",
    )
    parser.add_argument(
        "--ollama-timeout",
        type=int, # Original type was int, new was float. Sticking to original for consistency.
        default=20, # Original default was 20, new was 30.0. Sticking to original for consistency.
        help="Timeout for Ollama requests in seconds",
    )

    args = parser.parse_args(argv)

    try:
        pipeline = build_pipeline(args)
        sink_output = pipeline.run()
    except TypeFinderError as error:
        print(f"[error] {error}", file=sys.stderr)
        return 1
    except FileNotFoundError as error:
        print(f"[error] {error}", file=sys.stderr)
        return 1
    except Exception as e: # Catch other potential errors during pipeline execution
        print(f"[error] Error running pipeline: {e}", file=sys.stderr)
        return 1

    if sink_output:
        print(sink_output)
    else:
        print("[error] sink produced no output")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

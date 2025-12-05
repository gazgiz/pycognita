"""# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial"""
from __future__ import annotations

import argparse
import sys

from cognita.image_narrator import ImageNarrator
from cognita.ollama import OllamaClient
from cognita.pipeline import Pipeline
from cognita.sink import SilentSink
from cognita.source import DiscreteDataSource
from cognita.type_finder import TypeFinderError


def build_pipeline(args: argparse.Namespace) -> Pipeline:
    ollama_client = OllamaClient(
        model=args.ollama_model,
        base_url=args.ollama_url,
        timeout=args.ollama_timeout,
    )
    return Pipeline(
        [
            DiscreteDataSource(args.uri),
            ImageNarrator(ollama_client=ollama_client),
            SilentSink(),
        ]
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a detailed English description of an image.")
    parser.add_argument("uri", help="Path or file:// URI to the image.")
    parser.add_argument("--ollama-model", default="qwen2.5vl", help="Vision-capable Ollama model name.")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama base URL.")
    parser.add_argument("--ollama-timeout", type=int, default=20, help="HTTP timeout for Ollama requests.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pipeline = build_pipeline(args)

    try:
        sink_output = pipeline.run()
    except TypeFinderError as error:
        print(f"[error] {error}")
        return 1
    except FileNotFoundError as error:
        print(f"[error] {error}")
        return 1

    if sink_output:
        print(sink_output)
    else:
        print("[error] sink produced no output")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

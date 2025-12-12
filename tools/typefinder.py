# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial

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
    ollama_client = (
        None
        if args.no_ollama
        else OllamaClient(
            model=args.ollama_model,
            base_url=args.ollama_url,
            timeout=args.ollama_timeout,
        )
    )
    return Pipeline(
        [
            DiscreteDataSource(
                args.uri, prebuffer_bytes=args.prebuffer_bytes, ollama_client=ollama_client
            ),
            ImageNarrator(ollama_client=ollama_client),
            SilentSink(),
        ]
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Determine file type using header or Ollama fallback."
    )
    parser.add_argument("uri", help="URI/path to the data to inspect.")
    parser.add_argument(
        "--prebuffer-bytes",
        type=int,
        default=65_535,
        help="How many bytes to prebuffer for inspection (default: 65535).",
    )
    parser.add_argument("--no-ollama", action="store_true", help="Disable Ollama fallback.")
    parser.add_argument("--ollama-model", default="llama3.1", help="Ollama model name.")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama base URL.")
    parser.add_argument(
        "--ollama-timeout", type=int, default=10, help="HTTP timeout for Ollama requests."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pipeline = build_pipeline(args)

    try:
        sink_output = pipeline.run()
    except TypeFinderError as error:
        print(f"[error] {error}", file=sys.stderr)
        return 1
    except FileNotFoundError as error:
        print(f"[error] {error}", file=sys.stderr)
        return 1

    # SilentSink does not produce output; success if no exceptions encountered
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

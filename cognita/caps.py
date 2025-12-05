"""# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial"""
from __future__ import annotations

"""Core CAPS model and helpers.

Caps (capabilities) describe the semantic type of a file or payload. This small
module mirrors a subset of GStreamer CAPS ideas, with helpers to:
  - Represent a type as a frozen dataclass.
  - Render human-readable labels.
  - Produce RDF-like triples or Turtle snippets for downstream systems.

The goal is to keep type metadata explicit and easily serializable without
pulling in heavy dependencies.
"""

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Caps:
    """Simple capability descriptor (inspired by GStreamer's CAPS).

    Attributes:
        media_type: Broad MIME-style category (e.g., "image", "document").
        name: Short canonical name for the type.
        description: Optional human-friendly explanation.
        extensions: Optional file extensions associated with the type.
        uri: Optional canonical URI for RDF/linked-data style references.
        broader: Optional URIs for parent categories.
    """

    media_type: str
    name: str
    description: str | None = None
    extensions: Sequence[str] | None = None
    uri: str | None = None
    broader: Sequence[str] | None = None

    def label(self) -> str:
        """Return a display-friendly label, preferring name over media_type."""
        return self.name or self.media_type


def format_caps(caps: Caps) -> str:
    """Render a compact human-readable summary of a CAPS instance."""
    parts = [caps.media_type]
    if caps.extensions:
        parts.append(f"ext={','.join(caps.extensions)}")
    if caps.description:
        parts.append(caps.description)
    return " | ".join(parts)


def any_match(candidate: str, options: Iterable[str]) -> bool:
    """Case-insensitive equality check against a collection of options."""
    return any(candidate.lower() == option.lower() for option in options)


def caps_triples(caps: Caps) -> list[tuple[str, str, str]]:
    """Return a small RDF-like triple list for the CAPS item.

    The triples are tailored for lightweight linked-data use without requiring
    an RDF library. Predicates use a pseudo-namespace `pc:` for "pycognita".
    """
    subject = caps.uri or f"urn:cognita:caps:{caps.name}"
    triples = [
        (subject, "rdf:type", "pc:Caps"),
        (subject, "pc:mediaType", caps.media_type),
        (subject, "pc:name", caps.name),
    ]
    if caps.description:
        triples.append((subject, "pc:description", caps.description))
    if caps.extensions:
        for ext in caps.extensions:
            triples.append((subject, "pc:extension", ext))
    if caps.broader:
        for parent in caps.broader:
            triples.append((subject, "rdfs:subClassOf", parent))
    return triples


def caps_to_turtle(caps: Caps) -> str:
    """Serialize a Caps instance into a minimal Turtle string."""
    lines = [
        "@prefix pc: <urn:cognita:caps#> .",
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "",
    ]
    subj = f"<{caps.uri}>" if caps.uri else f"pc:{caps.name}"
    lines.append(f"{subj} a pc:Caps ;")
    lines.append(f'  pc:mediaType "{caps.media_type}" ;')
    lines.append(f'  pc:name "{caps.name}" ;')

    if caps.description:
        lines.append(f'  pc:description "{caps.description}" ;')
    if caps.extensions:
        ext_literals = ", ".join(f'"{ext}"' for ext in caps.extensions)
        lines.append(f"  pc:extension {ext_literals} ;")
    if caps.broader:
        broader_refs = ", ".join(f"<{uri}>" for uri in caps.broader)
        lines.append(f"  rdfs:subClassOf {broader_refs} ;")

    lines[-1] = lines[-1].rstrip(" ;") + " ."
    return "\n".join(lines)


def summarize_caps(caps: Caps, type_source: str | None = None) -> str:
    """Render a JSON summary suitable for CLI output."""
    import json

    summary = {
        "media_type": caps.media_type,
        "name": caps.name,
    }
    if caps.uri:
        summary["uri"] = caps.uri
    if caps.broader:
        summary["broader"] = ",".join(caps.broader)
    if caps.extensions:
        summary["extensions"] = ",".join(caps.extensions)
    if caps.description:
        summary["description"] = caps.description
    if type_source:
        summary["source"] = type_source
    return json.dumps(summary, ensure_ascii=True)

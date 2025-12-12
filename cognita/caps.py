# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial
"""Capabilities (Caps) handling using RDF/Check-lists.

Caps describe the type of data flowing through the pipeline.
They are essentially a set of RDF triples describing a Subject (the Content).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS

# Standard Namespaces (Manual to avoid SDO validation warnings)
SCHEMA = Namespace("https://schema.org/")

# Project Namespaces
PC = Namespace("urn:cognita:caps#")
PARAM = Namespace("urn:cognita:param:")


class Caps:
    """Describes the capabilities/type of a data stream or file.

    Internally backed by an rdflib.Graph.
    """

    def __init__(
        self,
        media_type: str | None = None,
        name: str | None = None,
        params: dict[str, Any] | None = None,
    ):
        self._graph = Graph()
        self._graph.bind("pc", PC)
        self._graph.bind("param", PARAM)
        self._graph.bind("dcterms", DCTERMS)
        self._graph.bind("schema", SCHEMA)

        params = params or {}

        # 1. Determine Identity (Subject)
        # If 'uri' is in params, use it. Otherwise, mint URN or BNode.
        uri = params.get("uri")
        if uri:
            self._node = URIRef(uri)
        elif name:
            # Stable URN for standard types (Hash URI for CURIE support)
            self._node = PC[name]
        else:
            self._node = BNode()

        self._graph.add((self._node, RDF.type, PC.Caps))

        # 2. Add Core Properties
        if media_type:
            self._graph.add((self._node, DCTERMS.format, Literal(media_type)))
        if name:
            self._graph.add((self._node, RDFS.label, Literal(name)))

        # 3. Add Params
        for key, value in params.items():
            if key == "uri":
                continue  # Handled
            self._add_param(key, value)

    def _add_param(self, key: str, value: Any) -> None:
        """Add a parameter to the graph, mapping logic to predicates."""
        predicate = self._map_key_to_predicate(key)

        values = value if isinstance(value, (list, tuple)) else [value]

        for v in values:
            usage_obj = self._to_rdf_object(key, v)
            self._graph.add((self._node, predicate, usage_obj))

    def _map_key_to_predicate(self, key: str) -> URIRef:
        if key == "description":
            return RDFS.comment
        elif key == "extensions":
            return SCHEMA["fileExtension"]
        elif key == "broader":
            return RDFS.subClassOf
        else:
            # Fallback to generic param namespace
            return PARAM[key]

    def _to_rdf_object(self, key: str, value: Any) -> URIRef | Literal:
        # If it looks like a URI, maybe return URIRef?
        # For now, strict mapping for "broader" which expects URIs often
        if key == "broader":
            return URIRef(str(value))
        return Literal(value)

    @property
    def media_type(self) -> str | None:
        """Get the media type (dcterms:format)."""
        val = self._graph.value(self._node, DCTERMS.format)
        return str(val) if val else None

    @property
    def name(self) -> str | None:
        """Get the short name (rdfs:label)."""
        val = self._graph.value(self._node, RDFS.label)
        return str(val) if val else None

    @property
    def uri(self) -> str:
        """Get the URI of this Caps node."""
        return str(self._node)

    @property
    def params(self) -> dict[str, Any]:
        """Reconstruct a params dictionary for backward compatibility.

        WARNING: This is lossy/approximate if multiple values exist for single-value expectations.
        """
        p = {}
        # We need to inverse map predicates to keys?
        # Or just dump everything we find?
        # Let's support the known keys at least.

        # description
        desc = self._graph.value(self._node, RDFS.comment)
        if desc:
            p["description"] = str(desc)

        # extensions (list)
        exts = []
        for o in self._graph.objects(self._node, SCHEMA.fileExtension):
            exts.append(str(o))
        if exts:
            p["extensions"] = tuple(exts)  # Tuple for compat

        # broader (list)
        broaders = []
        for o in self._graph.objects(self._node, RDFS.subClassOf):
            broaders.append(str(o))
        if broaders:
            p["broader"] = tuple(broaders)

        # uri
        p["uri"] = str(self._node)

        # Generic params
        generic_values = {}
        for _, p_pred, o in self._graph.triples((self._node, None, None)):
            if p_pred.startswith(PARAM):
                key = str(p_pred).replace(str(PARAM), "")

                val = o.value if isinstance(o, Literal) else str(o)

                if key not in generic_values:
                    generic_values[key] = []
                generic_values[key].append(val)

        for key, vals in generic_values.items():
            if len(vals) == 1:
                p[key] = vals[0]
            else:
                p[key] = vals  # Keep as list if multiple

        return p

    def merge_params(self, new_params: dict[str, Any]) -> Caps:
        """Return a NEW Caps object with merged parameters."""
        # This is slightly expensive: we have to extract current state and merge.
        # Or we can copy the graph.

        # Copy graph strategy
        new_graph = Graph()
        new_graph += self._graph  # add all triples

        # Create new instance but manually inject graph?
        # Cleaner: Re-instantiate from current params + new_params
        # because we moved to a graph-primary source of truth.
        current_data = self.params
        current_data.update(new_params)

        return Caps(media_type=self.media_type, name=self.name, params=current_data)

    def label(self) -> str:
        return self.name or self.media_type or "unknown"

    def __repr__(self) -> str:
        return f"Caps(media_type={self.media_type}, name={self.name})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Caps):
            return NotImplemented
        # Graph isomorphism is expensive.
        # Check basic properties + uri?
        # Or strict graph iso?
        # Let's try basic ISO
        from rdflib.compare import to_isomorphic

        return to_isomorphic(self._graph) == to_isomorphic(other._graph)


def format_caps(caps: Caps) -> str:
    parts = []
    if caps.media_type:
        parts.append(caps.media_type)

    exts = caps.params.get("extensions")
    if exts:
        parts.append(f"ext={','.join(exts)}")

    desc = caps.params.get("description")
    if desc:
        parts.append(desc)

    return " | ".join(parts)


def any_match(needle: str, haystack: Iterable[str]) -> bool:
    needle = needle.lower()
    return any(needle == h.lower() for h in haystack)


def caps_triples(caps: Caps) -> list[tuple[str, str, str]]:
    """Export triples as simple string tuples (legacy support)."""
    # Just iterate graph and str() everything
    triples = []
    for s, p, o in caps._graph:
        # Map well-known predicates to the 'pc:...' style if specifically requested by legacy tests?
        # Or just return full URIs?
        # Legacy code expects 'pc:mediaType', etc.
        # If I return full URIs, legacy tests fail.
        # I should probably update legacy tests to expect full URIs or CURIEs.
        # Let's return CURIEs if possible using graph's namespace manager.

        s_q = caps._graph.namespace_manager.normalizeUri(s)
        p_q = caps._graph.namespace_manager.normalizeUri(p)
        o_q = caps._graph.namespace_manager.normalizeUri(o) if isinstance(o, URIRef) else str(o)

        triples.append((s_q, p_q, o_q))

    return triples


def caps_to_turtle(caps: Caps) -> str:
    """Serialize caps to Turtle format."""
    return caps._graph.serialize(format="turtle")


def summarize_caps(caps: Caps, type_source: str = "unknown") -> str:
    """Return a JSON summary of the caps."""
    info = {
        "media_type": caps.media_type,
        "name": caps.name,
        "description": caps.params.get("description"),
        "source": type_source,
    }
    # Add other params
    p = caps.params
    for k, v in p.items():
        if k not in info:
            info[k] = v

    return json.dumps(info, indent=2)

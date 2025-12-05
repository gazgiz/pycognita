# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial
from __future__ import annotations

"""Element that extracts RDF triples from text using Ollama."""

from datetime import datetime
import uuid

from .caps import Caps
from .element import Element, PadDirection
from .narrator import TEXT_CAPS
from .ollama import OllamaClient, OllamaError

TURTLE_CAPS = Caps(
    media_type="text/turtle",
    name="rdf-turtle",
    description="RDF Triples in Turtle format.",
    extensions=("ttl",),
    uri="urn:cognita:caps:rdf-turtle",
    broader=("urn:cognita:caps:plain-text",),
)


class TripleExtractor(Element):
    """Extracts Knowledge Graph triples from plain text using an LLM.
    
    Attributes:
        tbox_template (str | None): Ontology schema to guide extraction.
        subject_iri (str | None): Base IRI for the subject. If None, generated automatically.
        min_text_length (int): Minimum text length required to attempt extraction.
    """

    def __init__(
        self,
        ollama_client: OllamaClient | None = None,
        tbox_template: str | None = None,
        subject_iri: str | None = None,
        min_text_length: int = 50,
    ):
        super().__init__()
        self.ollama_client = ollama_client or OllamaClient()
        self.tbox_template = tbox_template
        self.subject_iri = subject_iri
        self.min_text_length = min_text_length

    def process(self) -> None:
        pass  # Reactive element

    def on_buffer(self, pad, payload: object) -> None:
        # 1. Check upstream caps
        caps = getattr(pad, "caps", None)
        
        # 2. Check if we can process (must be plain text or compatible string payload)
        if not self._can_process(caps, payload):
            self._push_passthrough(payload)
            return

        # 3. Extract text
        text = self._extract_text(payload)
        if not text or len(text.strip()) < self.min_text_length:
             self._push_passthrough(payload)
             return

        # 4. Generate IRI if needed
        iri = self.subject_iri or self._generate_iri()

        # 5. Extract triples
        try:
            ttl_output = self._extract_triples(text, iri)
            if ttl_output:
                self._push_turtle(ttl_output)
            else:
                self._push_passthrough(payload)
        except OllamaError:
            self._push_passthrough(payload)

    def _can_process(self, caps: Caps | None, payload: object) -> bool:
        # 1. Check strict caps compatibility
        if isinstance(caps, Caps) and caps.name != "plain-text":
            return False

        # 2. Check permissive compatibility
        if isinstance(caps, Caps) and caps.name == "plain-text":
            return True
        if isinstance(payload, str):
            return True
        # Also accept standard Narrator output format
        if isinstance(payload, dict) and "image_description" in payload:
             return True
        return False

    def _extract_text(self, payload: object) -> str | None:
        if isinstance(payload, str):
            return payload
        if isinstance(payload, dict) and "image_description" in payload:
            return payload["image_description"]
        # Basic payload dict with data
        if isinstance(payload, dict) and b"data" in payload:
             try:
                 return payload[b"data"].decode("utf-8")
             except Exception:
                 return None
        return None

    def _generate_iri(self) -> str:
        timestamp = datetime.now().isoformat()
        return f"urn:cognita:generated:{timestamp}"

    def _extract_triples(self, text: str, subject_iri: str) -> str:
        prompt = (
            "You are a Knowledge Graph extractor. "
            "Extract Subject-Predicate-Object triples from the text below.\n"
            f"Use the Subject IRI: <{subject_iri}>\n"
        )
        
        if self.tbox_template:
            prompt += f"Follow this Ontology (TBox) strictly:\n{self.tbox_template}\n"
        else:
            prompt += "Use standard vocabulary (schema.org, foaf, dublin core) where possible.\n"

        prompt += (
            "\nOutput ONLY valid Turtle (TTL) syntax. "
            "Do not include markdown code blocks. "
            "Do not add explanations.\n\n"
            f"Text content:\n{text}"
        )

        return self.ollama_client._request(prompt)

    def _push_turtle(self, content: str) -> None:
        # Announce Turtle caps
        for pad in self.pads:
            if pad.direction == PadDirection.SRC:
                pad.set_caps(TURTLE_CAPS, propagate=True)
                pad.push(content)

    def _push_passthrough(self, payload: object) -> None:
        # Pass original payload downstream
        for pad in self.pads:
            if pad.direction == PadDirection.SRC and pad.peer:
                pad.peer.element.on_buffer(pad.peer, payload)

# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial
from __future__ import annotations

"""Element that extracts RDF triples from text using Ollama."""

from datetime import datetime
import uuid

from .caps import Caps
from .element import Element, PadDirection, CapsNegotiationError
from .narrator import TEXT_CAPS
from .ollama import OllamaClient, OllamaError

TURTLE_CAPS = Caps(
    media_type="text/turtle",
    name="rdf-turtle",
    params={
        "description": "RDF Triples in Turtle format.",
        "extensions": ("ttl",),
        "uri": "urn:cognita:caps:rdf-turtle",
        "broader": ("urn:cognita:caps:plain-text",),
    },
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

    def handle_event(self, pad, event: str, payload: object | None = None) -> None:
        """Handle control events, enforcing strict Caps compatibility."""
        if event == "caps":
            if not isinstance(payload, Caps):
                raise TypeError("TripleExtractor caps event requires Caps payload")
            
            # STRICT CHECK: Can we process these caps?
            if not self._can_process(payload, None):
                raise CapsNegotiationError(f"TripleExtractor cannot handle caps: {payload}")

            # Store upstream caps (but don't propagate blindly, we are a converter)
            pad.caps = payload
            return
        return super().handle_event(pad, event, payload)

    def on_buffer(self, pad, payload: object) -> None:
        # 1. Check upstream caps (assumed negotiated)
        caps = getattr(pad, "caps", None)
        
        # Runtime check
        if not self._can_process(caps, payload):
             return
 
        # 3. Extract text
        text = self._extract_text(payload)
        if not text or len(text.strip()) < self.min_text_length:
             return
 
        # 4. Generate IRI if needed
        iri = self.subject_iri or self._generate_iri(caps)
 
        # 5. Extract triples
        try:
            ttl_output = self._extract_triples(text, iri)
            if ttl_output:
                self._push_turtle(ttl_output)
        except OllamaError:
            # Runtime error, drop or log
            pass
 
    def _can_process(self, caps: Caps | None, payload: object | None) -> bool:
        # 1. Check strict caps compatibility
        if isinstance(caps, Caps) and caps.name != "plain-text":
            return False
 
        # 2. Check permissive compatibility (if payload provided)
        if isinstance(caps, Caps) and caps.name == "plain-text":
            return True
        if payload is not None:
            if isinstance(payload, str):
                return True
            # Also accept standard Narrator output format
            if isinstance(payload, dict) and "image_description" in payload:
                 return True
        elif caps is None:
             # If strictly checking caps only (payload=None), we are stricter.
             # We need explicit text caps or assumption of text.
             # For now, if no caps provided at all, we might be lenient or strict.
             # Let's be strict: if checking caps, and caps is None, return True 
             # (allow permissive/uncapped) or False?
             # Based on previous logic, we allowed uncapped.
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
 
    def _generate_iri(self, caps: Caps | None = None) -> str:
        # Strategy 1: Caps Fingerprint (Unified)
        if caps and caps.params.get("fingerprint"):
             fp = str(caps.params["fingerprint"])
             # If it looks like a Message-ID (contains @ or starts with <), use mail URN
             if fp.startswith("<") or "@" in fp:
                 clean_id = fp.strip("<>")
                 return f"urn:cognita:mail:{clean_id}"
             else:
                 # Assume hash
                 return f"urn:cognita:content:{fp}"
                 
        # Strategy 2: Fallback to Timestamp
        timestamp = datetime.now().isoformat()
        return f"urn:cognita:generated:{timestamp}"

    def _extract_triples(self, text: str, subject_iri: str) -> str:
        prompt = (
            "You are a Knowledge Graph extractor. "
            "Analyze the text below and extract Subject-Predicate-Object triples.\n"
            f"Subject IRI: <{subject_iri}>\n"
        )
        
        if self.tbox_template:
            prompt += f"Strictly use this Ontology (TBox) for predicates and classes:\n{self.tbox_template}\n"
        else:
            prompt += (
                "Use standard vocabularies (e.g., schema:, foaf:, dc:) for predicates. "
                "For unknown predicates, use a generic namespace ex:.\n"
            )

        prompt += (
            "\nExtraction Rules:\n"
            "1. The Subject IRI represents the **Image File** itself.\n"
            "2. You MUST link identified main entities to this Subject IRI first.\n"
            "   - Use `schema:image`, `ex:depicts`, or `ex:contains`.\n"
            "   - Example: `<SubjectIRI> ex:depicts ex:PlasticBag`.\n"
            "3. Then, extract relationships between entities.\n"
            "   - Example: `ex:PlasticBag ex:contains ex:Mulberries`.\n"
            "4. FORBIDDEN meta-predicates: 'hasContent', 'hasDescription' for visual objects.\n"
            "5. Structure: Entity -> Predicate -> Entity (or Literal).\n"
            "6. Use standard vocabularies (e.g., schema:, foaf:, dc:) or ex: for specific relations.\n"
        )

        prompt += (
            "\nOutput Guidelines:\n"
            "1. Format ONLY as valid Turtle (TTL).\n"
            "2. Do not emit markdown blocks (```turtle ... ```).\n"
            "3. If no triples can be extracted, output nothing.\n"
            "4. Ensure all prefixes are defined (@prefix ...).\n\n"
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

# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial
"""Element that extracts RDF triples from text using Ollama."""

from __future__ import annotations

from datetime import datetime

from .caps import Caps
from .element import CapsNegotiationError, Element, PadDirection
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
            ttl_output = self._extract_triples(text, iri, caps)
            if ttl_output:
                self._push_turtle(ttl_output)
        except OllamaError:
            # Runtime error, drop or log
            pass

    def _can_process(self, caps: Caps | None, payload: object | None) -> bool:
        # 1. Check strict caps compatibility
        if isinstance(caps, Caps) and caps.name != "plain-text":
            # Allow mail/mbox/image caps if we have text extractor logic for them
            # or if the payload is text/dict-with-text.
            # Ideally TripleExtractor should only see "narrated" text,
            # but currently we accept various caps if the payload is text-like.
            pass

        # 2. Check permissive compatibility (if payload provided)
        # (Existing logic maintained for compatibility)
        if isinstance(caps, Caps) and caps.name == "plain-text":
            return True
        if payload is not None:
            if isinstance(payload, str):
                return True
            # Also accept standard Narrator output format
            if isinstance(payload, dict) and "image_description" in payload:
                return True
        elif caps is None:
            return True

        # Allow mail-related caps if text is available
        # Allow mail-related caps if text is available
        return (
            isinstance(caps, Caps)
            and caps.name in ("application-mbox", "message-rfc822", "mail")
            and bool(payload)
            and isinstance(payload, (str, dict))
        )

    def _extract_text(self, payload: object) -> str | None:
        if isinstance(payload, str):
            return payload
        if isinstance(payload, dict) and "image_description" in payload:
            # Legacy image narrator output key
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

    def _get_extraction_rules(self, caps: Caps | None) -> str:
        """Return content-specific extraction rules."""
        from .prompt_loader import load_prompt

        # Load appropriate rules based on caps
        if caps and caps.name in ("application-mbox", "message-rfc822", "mail"):
             return load_prompt("triple_extractor_mail.txt")
        
        # Default/Generic rules
        return load_prompt("triple_extractor_default.txt")

    def _extract_triples(self, text: str, subject_iri: str, caps: Caps | None) -> str:
        from .prompt_loader import load_prompt
        
        rules = self._get_extraction_rules(caps)

        # Build TBox section
        if self.tbox_template:
            tbox_instruction = f"Strictly use this Ontology (TBox) for predicates and classes:\n{self.tbox_template}\n"
        else:
            tbox_instruction = (
                "Use standard vocabularies (e.g., schema:, foaf:, dc:) for predicates. "
                "For unknown predicates, use a generic namespace ex:.\n"
            )

        # Load system prompt template
        system_prompt = load_prompt("triple_extractor_system.txt")
        
        # Format the prompt
        # We need to map the template variables: {subject_iri}, {tbox_instruction}, {rules}, {text}
        prompt = system_prompt.format(
            subject_iri=subject_iri,
            tbox_instruction=tbox_instruction,
            rules=rules,
            text=text
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

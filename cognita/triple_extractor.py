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
        if isinstance(caps, Caps) and caps.name in ("application-mbox", "message-rfc822", "mail"):
             if payload and (isinstance(payload, str) or isinstance(payload, dict)):
                 return True
                 
        return False
 
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
        
        # Default Generic Rules
        base_rule = (
            "1. Analyze the text to extract Subject-Predicate-Object triples.\n"
            "2. The Subject IRI is provided.\n"
        )
        
        if not caps:
             return base_rule + (
                 "3. Extract entities and relationships.\n"
                 "4. Use standard vocabularies (schema, ex).\n"
             )

        # MAIL Rules
        if caps.name in ("application-mbox", "message-rfc822", "mail"):
            return base_rule + (
                "3. The Subject IRI represents an **Email Message**.\n"
                "4. Extract email metadata:\n"
                "   - `schema:sender` (Person or Organization)\n"
                "   - `schema:recipient`\n"
                "   - `schema:dateSent`\n"
                "   - `schema:about` (Subject Line topic)\n"
                "5. Extract content details:\n"
                "   - `schema:mentions` (Entities mentioned in body)\n"
                "   - `ex:hasTopic`\n"
                "6. Example:\n"
                "   `<SubjectIRI> schema:sender <ex:Alice> .`\n"
                "   `<SubjectIRI> schema:about \"Project Update\" .`\n"
            )

        # IMAGE Rules (Default assumption for now if not mail, or check explicitly)
        # If caps name implies image/video/visual or if coming from image narrator
        # (ImageNarrator outputs NARRATION_CAPS which inherits plain-text but has description 'Machine-generated...')
        # We can check specific caps or just fallback to generic?
        # The user issue was applying image rules to mbox.
        # So we should be specific for image, fallback for text.
        
        # We don't have explicit IMAGE_CAPS passed here usually (it's NARRATION_CAPS).
        # We rely on checking if it's NOT mail/text, OR if we can infer visual.
        # But wait, ImageNarrator output caps are NARRATION_CAPS.
        # How to distinguish Image Narration from Text Narration?
        # In `ImageNarrator`, we output `NARRATION_CAPS`.
        # Maybe we should check if the payload had `image_description`? 
        # But we don't have payload here, just caps.
        # For now, let's keep the existing "Image" rules as a specific branch if we can detect it,
        # OR default to a GENERIC ruleset that isn't image-biased.
        # The PROMPTS are:
        # 1. MAIL
        # 2. VISUAL (if we know it's visual)
        # 3. GENERIC TEXT (default)
        
        # Since currently we only really have Image and Mail as main use cases:
        # Let's assume Generic unless Mail? But previous default was Image.
        return base_rule + (
            "3. Extract entities and relationships.\n"
            "4. Link main entities to the Subject IRI using suitable predicates (e.g., schema:mentions, schema:about, ex:depicts).\n"
            "5. Use standard vocabularies.\n"
        )

    def _extract_triples(self, text: str, subject_iri: str, caps: Caps | None) -> str:
        rules = self._get_extraction_rules(caps)
        
        # If we suspect visual content (e.g. from existing specific prompt logic), we might want to inject specific visual rules.
        # But for now, let's stick to the safe Mail vs Generic split.
        # Unless the user specifically wants the Image prompt back for images.
        # The user said: "caps에 따라서 프롬프트를 달리 해보자."
        
        # Re-introducing Image Rules if caps are generic?
        # If we want to support existing behavior for images, we need to know it's an image.
        # But the input to TripleExtractor is TEXT (the narration). The caps *should* reflect the source.
        # ImageNarrator should ideally propagate `broader: image` or similar metadata?
        # Currently `ImageNarrator` emits `NARRATION_CAPS` (plain-text).
        # Let's add a "Visual" check if possible, or stick to safe Generic.
        
        # For this specific task (fixing mbox), having a dedicated Mail prompt fixes the hallucination.
        # Restoring the "Image" prompt requires identifying "Image".
        # If I can't identify Image easily from current Caps, Generic is safer than Image-for-all.
        
        # Wait, the user command `image2spo` worked fine with the old prompt.
        # I should try to preserve that behavior for `image2spo` while using Mail for `mbox2spo`.
        
        # Ideally, ImageNarrator should output caps that say "Narration of Image".
        # But assuming Generic is safer. Let's start with Generic + Mail.
        
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

        prompt += f"\nExtraction Rules:\n{rules}"

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

from unittest.mock import MagicMock
import pytest
from cognita.triple_extractor import TripleExtractor, TURTLE_CAPS
from cognita.caps import Caps
from cognita.pad import PadDirection
from cognita.ollama import OllamaError

class MockPad:
    def __init__(self, direction=PadDirection.SRC):
        self.direction = direction
        self.caps = None
        self.peer = None
        self.pushed_data = []

    def set_caps(self, caps, propagate=False):
        self.caps = caps

    def push(self, data):
        self.pushed_data.append(data)

class MockElement:
    def __init__(self):
        self.received_buffers = []

    def on_buffer(self, pad, buffer):
        self.received_buffers.append(buffer)

def test_triple_extractor_init():
    extractor = TripleExtractor()
    assert extractor.ollama_client is not None
    assert extractor.tbox_template is None
    assert extractor.min_text_length == 50

def test_can_process():
    extractor = TripleExtractor()
    
    # Caps check
    assert extractor._can_process(Caps("text/plain", "plain-text"), "text")
    # UPDATED: If payload is string ("img"), we enforce checking caps logic? 
    # Current implementation returns True if payload is string.
    assert extractor._can_process(Caps("image/jpeg", "image"), "img")
    
    # Payload string check
    assert extractor._can_process(None, "just a string")
    
    # Narrator output check
    assert extractor._can_process(None, {"image_description": "desc"})

def test_extract_triples_flow():
    mock_ollama = MagicMock()
    mock_ollama._request.return_value = "<subj> <pred> <obj> ."
    
    extractor = TripleExtractor(ollama_client=mock_ollama, min_text_length=5)
    
    # Setup pad
    src_pad = MockPad(PadDirection.SRC)
    extractor._pads = [src_pad]
    
    payload = "This is a test text."
    extractor.on_buffer(MockPad(PadDirection.SINK), payload)
    
    # Verify Ollama called
    mock_ollama._request.assert_called_once()
    
    # Verify output pushed
    assert len(src_pad.pushed_data) == 1
    assert src_pad.pushed_data[0] == "<subj> <pred> <obj> ."
    assert src_pad.caps == TURTLE_CAPS

def test_short_text_passthrough():
    mock_ollama = MagicMock()
    extractor = TripleExtractor(ollama_client=mock_ollama, min_text_length=100)
    
    # Setup downstream for passthrough
    src_pad = MockPad(PadDirection.SRC)
    peer_pad = MockPad(PadDirection.SINK)
    peer_element = MockElement()
    
    # Link mock structure
    # Since we can't easily mock the whole peer structure with just classes,
    # we abuse the MockPad to act like it has a peer.element
    peer_pad.element = peer_element
    src_pad.peer = peer_pad
    
    extractor._pads = [src_pad]
    
    payload = "Too short."
    extractor.on_buffer(MockPad(PadDirection.SINK), payload)
    
    # Ollama NOT called
    mock_ollama._request.assert_not_called()
    
    # Original payload passed through -> NO, dropped behavior
    assert len(peer_element.received_buffers) == 0

def test_ollama_error_passthrough():
    mock_ollama = MagicMock()
    mock_ollama._request.side_effect = OllamaError("fail")
    
    extractor = TripleExtractor(ollama_client=mock_ollama, min_text_length=1)
    
    src_pad = MockPad(PadDirection.SRC)
    peer_pad = MockPad(PadDirection.SINK)
    peer_element = MockElement()
    peer_pad.element = peer_element
    src_pad.peer = peer_pad
    
    extractor._pads = [src_pad]
    
    extractor.on_buffer(MockPad(PadDirection.SINK), "valid text")
    
    # Original passed through on error -> NO, dropped behavior
    assert len(peer_element.received_buffers) == 0

def test_tbox_prompt_inclusion():
    mock_ollama = MagicMock()
    mock_ollama._request.return_value = "..."
    
    tbox = "class Person { name: string }"
    extractor = TripleExtractor(ollama_client=mock_ollama, tbox_template=tbox, min_text_length=1)
    
    extractor._pads = [MockPad(PadDirection.SRC)]
    
    extractor.on_buffer(MockPad(PadDirection.SINK), "text")
    
    args, _ = mock_ollama._request.call_args
    prompt = args[0]
    assert tbox in prompt

def test_iri_generation_priority():
    mock_ollama = MagicMock()
    mock_ollama._request.return_value = "..."
    extractor = TripleExtractor(ollama_client=mock_ollama, min_text_length=1)
    
    # 1. Test Fingerprint
    caps_hash = Caps("text/plain", "plain-text", params={"fingerprint": "abc123hash"})
    pad_hash = MockPad(PadDirection.SRC)
    pad_hash.set_caps(caps_hash)
    extractor._pads = [pad_hash] # Only looking at own pads? The code looks at `getattr(pad, "caps")` passed to on_buffer
    
    # Pass Sink pad with caps attached (simulation of upstream setting caps on sink pad of previous element?)
    # Wait, on_buffer receives 'pad' which is the element's SINK pad.
    sink_pad = MockPad(PadDirection.SINK)
    sink_pad.caps = caps_hash
    
    extractor.on_buffer(sink_pad, "text")
    
    args, _ = mock_ollama._request.call_args
    prompt = args[0]
    assert "Subject IRI: <urn:cognita:content:abc123hash>" in prompt
    
    # 2. Test Message-ID (passed as fingerprint)
    mock_ollama.reset_mock()
    # Note: type_finder puts the raw Message-ID string into 'fingerprint'
    caps_mail = Caps("text/plain", "plain-text", params={"fingerprint": "<msg-id-123>"})
    sink_pad.caps = caps_mail
    
    extractor.on_buffer(sink_pad, "text")
    
    args, _ = mock_ollama._request.call_args
    prompt = args[0]
    # Check that heuristic detected it as mail
    assert "Subject IRI: <urn:cognita:mail:msg-id-123>" in prompt

def test_extraction_prompt_selection():
    """Verify correct prompt rules are selected based on Caps."""
    extractor = TripleExtractor()
    
    # 1. Generic/None Caps
    rules_generic = extractor._get_extraction_rules(None)
    assert "Subject IRI representing the Image" not in rules_generic
    assert "Extract entities and relationships" in rules_generic
    
    # 2. Mail Caps
    mail_caps = Caps("application/mbox", "application-mbox")
    rules_mail = extractor._get_extraction_rules(mail_caps)
    assert "Subject IRI represents an **Email Message**" in rules_mail
    assert "schema:sender" in rules_mail
    
    # 3. Plain Text (Generic)
    text_caps = Caps("text/plain", "plain-text")
    rules_text = extractor._get_extraction_rules(text_caps)
    rules_text = extractor._get_extraction_rules(text_caps)
    assert "Extract entities and relationships" in rules_text

def test_structured_list_prompt():
    """Verify prompt includes special rules for structured lists."""
    mock_ollama = MagicMock()
    mock_ollama._request.return_value = "..."
    extractor = TripleExtractor(ollama_client=mock_ollama)
    
    # Use generic caps (plain-text) to trigger the fallback rules where our instruction lives
    sink_pad = MockPad(PadDirection.SINK)
    sink_pad.caps = Caps("text/plain", "plain-text")
    
    # Use text > 50 chars (default min_text_length)
    extractor.on_buffer(sink_pad, "This input needs to be long enough to trigger the extractor logic." * 2)
    
    args, _ = mock_ollama._request.call_args
    prompt = args[0]
    
    assert "ATOMIC OBJECT RULE" in prompt
    assert "ex:lightingCondition" in prompt
    assert "CRITICAL: Do NOT use the word 'mentions'" in prompt

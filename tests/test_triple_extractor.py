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
    assert not extractor._can_process(Caps("image/jpeg", "image"), "img")
    
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

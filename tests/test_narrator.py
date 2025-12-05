from unittest.mock import MagicMock
import pytest
from cognita.narrator import Narrator, NARRATION_CAPS
from cognita.caps import Caps
from cognita.pad import Pad, PadDirection

class ConcreteNarrator(Narrator):
    def __init__(self):
        super().__init__()
        self.can_process_result = False
        self.narrate_result = None

    def _can_process(self, caps, payload):
        return self.can_process_result

    def _narrate(self, payload, caps):
        return self.narrate_result

def test_narrator_passthrough():
    narrator = ConcreteNarrator()
    narrator.can_process_result = False
    
    # Setup pads
    sink_pad = narrator.request_pad(PadDirection.SINK)
    src_pad = narrator.request_pad(PadDirection.SRC)
    
    # Mock peer
    mock_peer = MagicMock()
    mock_peer.direction = PadDirection.SINK
    src_pad.peer = mock_peer
    
    payload = "input data"
    narrator.on_buffer(sink_pad, payload)
    
    mock_peer.element.on_buffer.assert_called_with(mock_peer, payload)

def test_narrator_success():
    narrator = ConcreteNarrator()
    narrator.can_process_result = True
    narrator.narrate_result = "description"
    
    # Setup pads
    sink_pad = narrator.request_pad(PadDirection.SINK)
    src_pad = narrator.request_pad(PadDirection.SRC)
    
    # Mock peer
    mock_peer = MagicMock()
    mock_peer.direction = PadDirection.SINK
    src_pad.peer = mock_peer
    
    caps = Caps("media/type", "test")
    # Simulate caps present on pad
    sink_pad.caps = caps
    
    narrator.on_buffer(sink_pad, "payload")
    
    # Should push description
    mock_peer.element.on_buffer.assert_called_with(mock_peer, "description")
    
    # Should have propagated NARRATION_CAPS
    assert src_pad.caps == NARRATION_CAPS
    mock_peer.element.handle_event.assert_called_with(mock_peer, "caps", NARRATION_CAPS)

def test_narrator_failure_no_output():
    narrator = ConcreteNarrator()
    narrator.can_process_result = True
    narrator.narrate_result = None
    
    # Setup pads
    src_pad = narrator.request_pad(PadDirection.SRC)
    mock_peer = MagicMock()
    mock_peer.direction = PadDirection.SINK
    src_pad.peer = mock_peer
    
    narrator.on_buffer(None, "payload")
    
    mock_peer.element.on_buffer.assert_not_called()

def test_handle_event_caps_propagation():
    narrator = ConcreteNarrator()
    
    # Setup pads
    sink_pad = narrator.request_pad(PadDirection.SINK)
    src_pad = narrator.request_pad(PadDirection.SRC)
    
    mock_peer = MagicMock()
    mock_peer.direction = PadDirection.SINK
    mock_peer.element = MagicMock() # Ensure element is also a mock
    
    # Link manually for test
    src_pad.peer = mock_peer
    mock_peer.peer = src_pad

    caps = Caps("test/caps", "test")
    narrator.handle_event(sink_pad, "caps", caps)
    
    assert sink_pad.caps == caps
    assert narrator._caps == caps
    
    # Check propagation
    assert mock_peer.caps == caps
    mock_peer.element.handle_event.assert_called_with(mock_peer, "caps", caps)

from unittest.mock import MagicMock
import pytest
from cognita.narrator import Narrator, NARRATION_CAPS
from cognita.caps import Caps
from cognita.pad import Pad, PadDirection
from cognita.element import CapsNegotiationError

class ConcreteNarrator(Narrator):
    def __init__(self):
        super().__init__()
        self.can_process_result = True
        self.narrate_result = "description"

    def _can_process(self, caps, payload):
        return self.can_process_result

    def _narrate(self, payload, caps):
        return self.narrate_result

def test_caps_negotiation_success():
    narrator = ConcreteNarrator()
    narrator.can_process_result = True
    
    pad = narrator.request_pad(PadDirection.SINK)
    caps = Caps("media/test", "test")
    
    # Should succeed
    narrator.handle_event(pad, "caps", caps)
    
    assert pad.caps == caps
    assert narrator._caps == caps

def test_caps_negotiation_failure():
    narrator = ConcreteNarrator()
    narrator.can_process_result = False
    
    pad = narrator.request_pad(PadDirection.SINK)
    caps = Caps("media/bad", "bad")
    
    # Should raise error immediately
    with pytest.raises(CapsNegotiationError):
        narrator.handle_event(pad, "caps", caps)

def test_narrator_process_flow():
    narrator = ConcreteNarrator()
    narrator.can_process_result = True
    narrator.narrate_result = "generated text"
    
    # Setup pads
    sink_pad = narrator.request_pad(PadDirection.SINK)
    src_pad = narrator.request_pad(PadDirection.SRC)
    
    # Mock peer
    mock_peer = MagicMock()
    mock_peer.direction = PadDirection.SINK
    src_pad.peer = mock_peer
    
    # 1. Negotiate Caps
    caps = Caps("media/input", "input")
    sink_pad.caps = caps
    narrator._caps = caps 
    
    # 2. Process Buffer
    narrator.on_buffer(sink_pad, "payload")
    
    # Should verify output caps were announced
    mock_peer.element.handle_event.assert_called_with(mock_peer, "caps", NARRATION_CAPS)
    
    # Should verify output data pushed
    mock_peer.element.on_buffer.assert_called_with(mock_peer, "generated text")

def test_narrator_runtime_reject():
    """Verify that even if caps passed, runtime rejection stops flow (no passthrough)."""
    narrator = ConcreteNarrator()
    narrator.can_process_result = False # Simulate runtime rejection (e.g. file missing)
    
    sink_pad = narrator.request_pad(PadDirection.SINK)
    src_pad = narrator.request_pad(PadDirection.SRC)
    
    mock_peer = MagicMock()
    mock_peer.direction = PadDirection.SINK
    src_pad.peer = mock_peer
    
    narrator.on_buffer(sink_pad, "bad payload")
    
    # Should NOT call downstream (no passthrough)
    mock_peer.element.on_buffer.assert_not_called()

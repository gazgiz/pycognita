import pytest
from cognita.pad import Pad, PadDirection
from cognita.element import Element

class MockElement(Element):
    def __init__(self):
        super().__init__()
        self.received_buffers = []
        self.received_events = []

    def on_buffer(self, pad, buffer):
        self.received_buffers.append((pad, buffer))

    def handle_event(self, pad, event, payload=None):
        self.received_events.append((pad, event, payload))

def test_pad_init():
    el = MockElement()
    pad = Pad("test", PadDirection.SRC, el)
    assert pad.name == "test"
    assert pad.direction == PadDirection.SRC
    assert pad.element == el
    assert pad.peer is None

def test_pad_link_success():
    el1 = MockElement()
    src = Pad("src", PadDirection.SRC, el1)
    
    el2 = MockElement()
    sink = Pad("sink", PadDirection.SINK, el2)
    
    src.link(sink)
    assert src.peer == sink
    assert sink.peer == src

def test_pad_link_errors():
    el = MockElement()
    src1 = Pad("src1", PadDirection.SRC, el)
    src2 = Pad("src2", PadDirection.SRC, el)
    sink = Pad("sink", PadDirection.SINK, el)
    
    # Same direction
    with pytest.raises(ValueError, match="directions must be opposite"):
        src1.link(src2)
        
    # Already linked
    src1.link(sink)
    with pytest.raises(ValueError, match="already linked"):
        src1.link(sink)

def test_pad_push():
    el_src = MockElement()
    src = Pad("src", PadDirection.SRC, el_src)
    
    el_sink = MockElement()
    sink = Pad("sink", PadDirection.SINK, el_sink)
    
    src.link(sink)
    
    src.push("data")
    assert len(el_sink.received_buffers) == 1
    assert el_sink.received_buffers[0] == (sink, "data")

def test_pad_push_error():
    el = MockElement()
    sink = Pad("sink", PadDirection.SINK, el)
    
    with pytest.raises(ValueError, match="only valid on src pads"):
        sink.push("data")
        
    src = Pad("src", PadDirection.SRC, el)
    with pytest.raises(ValueError, match="not linked"):
        src.push("data")

def test_pad_caps_propagation():
    el_src = MockElement()
    src = Pad("src", PadDirection.SRC, el_src)
    
    el_sink = MockElement()
    sink = Pad("sink", PadDirection.SINK, el_sink)
    
    src.link(sink)
    
    caps = "fake-caps"
    src.set_caps(caps, propagate=True)
    
    assert src.caps == caps
    assert len(el_sink.received_events) == 1
    assert el_sink.received_events[0] == (sink, "caps", caps)

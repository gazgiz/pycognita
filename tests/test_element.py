import pytest
from cognita.element import Element, SourceElement, SinkElement
from cognita.pad import PadDirection
from cognita.caps import Caps

class ConcreteElement(Element):
    def process(self):
        pass
    def on_buffer(self, pad, buffer):
        pass

def test_element_request_pad():
    el = ConcreteElement()
    pad_src = el.request_pad(PadDirection.SRC, "src")
    assert pad_src.name == "src"
    assert pad_src.direction == PadDirection.SRC
    assert pad_src.element == el
    assert pad_src in el.pads

    pad_sink = el.request_pad(PadDirection.SINK)
    assert pad_sink.name == "sink1"  # "sink" + len(pads) which is 1
    assert pad_sink.direction == PadDirection.SINK

def test_element_handle_event_caps():
    el = ConcreteElement()
    pad = el.request_pad(PadDirection.SINK, "sink")
    caps = Caps("text/plain", "text")
    
    el.handle_event(pad, "caps", caps)
    assert pad.caps == caps

def test_element_handle_event_invalid_caps():
    el = ConcreteElement()
    pad = el.request_pad(PadDirection.SINK, "sink")
    
    with pytest.raises(TypeError):
        el.handle_event(pad, "caps", "not-caps-object")

def test_element_handle_event_unhandled():
    el = ConcreteElement()
    pad = el.request_pad(PadDirection.SINK, "sink")
    
    with pytest.raises(NotImplementedError):
        el.handle_event(pad, "unknown-event")

def test_source_element_restrictions():
    src_el = SourceElement()
    src_el.request_pad(PadDirection.SRC, "src")
    
    with pytest.raises(ValueError):
        src_el.request_pad(PadDirection.SINK, "sink")

def test_sink_element_restrictions():
    sink_el = SinkElement()
    sink_el.request_pad(PadDirection.SINK, "sink")
    
    with pytest.raises(ValueError):
        sink_el.request_pad(PadDirection.SRC, "src")

from unittest.mock import MagicMock
from cognita.pipeline import Pipeline, link_many
from cognita.element import Element
from cognita.pad import PadDirection

class MockElement(Element):
    def __init__(self, name="mock"):
        super().__init__()
        self.name = name
        self.process_called = False
        self.output = None

    def process(self):
        self.process_called = True

    def on_buffer(self, pad, buffer):
        pass

def test_link_many():
    el1 = MockElement("el1")
    el2 = MockElement("el2")
    el3 = MockElement("el3")
    
    link_many(el1, el2, el3)
    
    # Check link el1 -> el2
    assert len(el1.pads) == 1
    assert len(el2.pads) == 2 # sink from el1, src to el3 (wait, link_many only creates pads needed)
    # Actually link_many(a, b, c) does:
    # a.req(src) -> b.req(sink)
    # b.req(src) -> c.req(sink)
    
    assert el1.pads[0].direction == PadDirection.SRC
    assert el1.pads[0].peer.element == el2
    assert el1.pads[0].peer.direction == PadDirection.SINK
    
    # Check link el2 -> el3
    # el2 has sink (index 0) and src (index 1)
    pads_el2 = el2.pads
    assert pads_el2[0].direction == PadDirection.SINK
    assert pads_el2[1].direction == PadDirection.SRC
    assert pads_el2[1].peer.element == el3
    
    assert len(el3.pads) == 1
    assert el3.pads[0].direction == PadDirection.SINK

def test_pipeline_init_links():
    el1 = MockElement("el1")
    el2 = MockElement("el2") 
    
    pipeline = Pipeline([el1, el2])
    
    assert len(el1.pads) == 1
    assert len(el2.pads) == 1
    assert el1.pads[0].peer == el2.pads[0]

def test_pipeline_run():
    el1 = MockElement("el1")
    el2 = MockElement("el2")
    el2.output = "final_result"
    
    pipeline = Pipeline([el1, el2])
    result = pipeline.run()
    
    assert el1.process_called
    assert el2.process_called
    assert result == "final_result"

def test_link_many_empty():
    # Should not crash
    link_many()
    link_many(MockElement())

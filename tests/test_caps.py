import json
from cognita.caps import Caps, format_caps, any_match, caps_triples, caps_to_turtle, summarize_caps

def test_caps_creation_and_label():
    caps = Caps(media_type="image/jpeg", name="jpeg", description="JPEG Image", extensions=["jpg", "jpeg"])
    assert caps.media_type == "image/jpeg"
    assert caps.name == "jpeg"
    assert caps.label() == "jpeg"
    
    caps_no_name = Caps(media_type="text/plain", name="", description="Text")
    assert caps_no_name.label() == "text/plain"

def test_format_caps():
    caps = Caps(media_type="image/png", name="png", extensions=["png"], description="PNG Image")
    formatted = format_caps(caps)
    assert "image/png" in formatted
    assert "ext=png" in formatted
    assert "PNG Image" in formatted
    
    caps_simple = Caps(media_type="application/octet-stream", name="binary")
    assert format_caps(caps_simple) == "application/octet-stream"

def test_any_match():
    assert any_match("jpg", ["JPG", "png"])
    assert any_match("PNG", ["jpg", "png"])
    assert not any_match("gif", ["jpg", "png"])

def test_caps_triples():
    caps = Caps(
        media_type="video/mp4", 
        name="mp4", 
        extensions=["mp4"], 
        description="MPEG-4 Video",
        uri="http://example.org/types/mp4",
        broader=["http://example.org/types/video"]
    )
    triples = caps_triples(caps)
    
    assert (caps.uri, "rdf:type", "pc:Caps") in triples
    assert (caps.uri, "pc:mediaType", "video/mp4") in triples
    assert (caps.uri, "pc:name", "mp4") in triples
    assert (caps.uri, "pc:description", "MPEG-4 Video") in triples
    assert (caps.uri, "pc:extension", "mp4") in triples
    assert (caps.uri, "rdfs:subClassOf", "http://example.org/types/video") in triples

def test_caps_to_turtle():
    caps = Caps(media_type="audio/mpeg", name="mp3", extensions=["mp3"])
    turtle = caps_to_turtle(caps)
    
    assert "@prefix pc: <urn:cognita:caps#> ." in turtle
    assert "pc:mp3 a pc:Caps ;" in turtle
    assert 'pc:mediaType "audio/mpeg" ;' in turtle
    assert 'pc:extension "mp3" .' in turtle

def test_summarize_caps():
    caps = Caps(media_type="text/markdown", name="markdown", description="Markdown")
    summary_json = summarize_caps(caps, type_source="libmagic")
    summary = json.loads(summary_json)
    
    assert summary["media_type"] == "text/markdown"
    assert summary["name"] == "markdown"
    assert summary["description"] == "Markdown"
    assert summary["source"] == "libmagic"

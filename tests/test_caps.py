
import json
from cognita.caps import Caps, format_caps, any_match, caps_triples, caps_to_turtle, summarize_caps

def test_caps_creation_and_label():
    caps = Caps(media_type="image/jpeg", name="jpeg", params={"description": "JPEG Image", "extensions": ["jpg", "jpeg"]})
    assert caps.media_type == "image/jpeg"
    assert caps.name == "jpeg"
    assert caps.label() == "jpeg"
    
    # Check if data is internally in the graph (implicit check via property)
    assert caps.params["description"] == "JPEG Image"

def test_format_caps():
    caps = Caps(media_type="image/png", name="png", params={"extensions": ["png"], "description": "PNG Image"})
    formatted = format_caps(caps)
    assert "image/png" in formatted
    assert "ext=png" in formatted
    assert "PNG Image" in formatted

def test_caps_triples_standard_ontologies():
    """Verify that Caps exposes standard ontology predicates now."""
    caps = Caps(
        media_type="video/mp4", 
        name="mp4", 
        params={
            "extensions": ["mp4"], 
            "description": "MPEG-4 Video",
            "broader": ["http://example.org/types/video"]
        }
    )
    triples = caps_triples(caps)
    # uri property returns full URI, but triples via caps_triples uses CURIEs
    # because 'pc' prefix is bound to 'urn:cognita:caps#'
    
    subject_curie = "pc:mp4"
    
    assert (subject_curie, "rdf:type", "pc:Caps") in triples
    assert (subject_curie, "dcterms:format", "video/mp4") in triples
    assert (subject_curie, "rdfs:label", "mp4") in triples
    assert (subject_curie, "rdfs:comment", "MPEG-4 Video") in triples
    assert (subject_curie, "schema:fileExtension", "mp4") in triples
    # Objects that are URIs might be normalized too if prefixes match, 
    # but http://example.org/types/video likely has no prefix bound, so it gets <>
    assert (subject_curie, "rdfs:subClassOf", "<http://example.org/types/video>") in triples

def test_caps_to_turtle():
    caps = Caps(media_type="audio/mpeg", name="mp3", params={"extensions": ["mp3"]})
    turtle = caps_to_turtle(caps)
    
    # Check for standard prefixes
    assert "@prefix dcterms: <http://purl.org/dc/terms/> ." in turtle
    assert "@prefix schema: <https://schema.org/> ." in turtle
    
    # Check content
    assert "dcterms:format \"audio/mpeg\"" in turtle
    assert "schema:fileExtension \"mp3\"" in turtle

def test_summarize_caps():
    caps = Caps(media_type="text/markdown", name="markdown", params={"description": "Markdown"})
    summary_json = summarize_caps(caps, type_source="libmagic")
    summary = json.loads(summary_json)
    
    assert summary["media_type"] == "text/markdown"
    assert summary["name"] == "markdown"
    assert summary["description"] == "Markdown"

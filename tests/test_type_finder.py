from cognita.type_finder import HeaderAnalyzer, DEFAULT_DETECTORS

def test_detect_pdf():
    analyzer = HeaderAnalyzer()
    data = b"%PDF-1.4 header"
    caps = analyzer.detect(data)
    assert caps.name == "document"
    assert "pdf" in caps.extensions

def test_detect_png():
    analyzer = HeaderAnalyzer()
    data = b"\x89PNG\r\n\x1a\n\x00\x00"
    caps = analyzer.detect(data)
    assert caps.name == "image-photo"
    assert "png" in caps.extensions

def test_detect_jpeg():
    analyzer = HeaderAnalyzer()
    data = b"\xff\xd8\xff\xe0\x00"
    caps = analyzer.detect(data)
    assert caps.name == "image-photo"
    assert "jpg" in caps.extensions

def test_detect_mbox():
    analyzer = HeaderAnalyzer()
    data = b"From user Fri Jul  8 12:00:00 2011\nSubject: Hi"
    caps = analyzer.detect(data)
    assert caps.name == "mail"
    assert "mbox" in caps.extensions

def test_detect_eml():
    analyzer = HeaderAnalyzer()
    data = b"Subject: Hello\nFrom: sender@example.com\n"
    caps = analyzer.detect(data)
    assert caps.name == "mail"
    assert "eml" in caps.extensions

def test_detect_mp4():
    analyzer = HeaderAnalyzer()
    data = b"\x00\x00\x00\x18ftypmp42"
    caps = analyzer.detect(data)
    assert caps.name == "video"
    assert "mp4" in caps.extensions

def test_detect_zip():
    analyzer = HeaderAnalyzer()
    data = b"PK\x03\x04\x0a\x00\x00\x00"
    caps = analyzer.detect(data)
    assert caps.name == "binary-file" 
    # Note: might be overridden by ooxml check if we crafted a specific zip, 
    # but generic zip is binary.

def test_detect_ooxml():
    analyzer = HeaderAnalyzer()
    # Needs to contain [Content_Types].xml or similar
    data = b"PK\x03\x04" + b"A" * 50 + b"[Content_Types].xml"
    caps = analyzer.detect(data)
    assert caps.name == "document" # ooxml-zip maps to document caps

def test_detect_text_document():
    analyzer = HeaderAnalyzer()
    data = b"This is just some plain text content that is mostly ASCII." * 10
    caps = analyzer.detect(data)
    assert caps.name == "document"
    assert "txt" in caps.extensions

def test_detect_unknown():
    analyzer = HeaderAnalyzer()
    data = b"\x00\x01\x02" * 10  # Binary noise
    caps = analyzer.detect(data)
    assert caps is None

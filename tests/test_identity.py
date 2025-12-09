
import os
import hashlib
import tempfile
import pytest
from unittest.mock import MagicMock
from cognita.source import DiscreteDataSource
from cognita.caps import Caps
from cognita.pad import Pad, PadDirection

@pytest.fixture
def mock_pad():
    pad = MagicMock(spec=Pad)
    pad.direction = PadDirection.SRC
    return pad

def test_fingerprint_generic_file(mock_pad):
    """Test that a generic binary file gets a SHA-256 fingerprint."""
    content = b"random binary content for fingerprinting"
    expected_hash = hashlib.sha256(content).hexdigest()
    
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
        
    try:
        uri = f"file://{tmp_path}"
        source = DiscreteDataSource(uri=uri)
        source._pads = [mock_pad]
        
        # Mock header analyzer to return BINARY_CAPS or let it detect text
        # But simplify by mocking _detect_caps logic implicitly via process() 
        # Actually easier to just run process() and let it use real detection
        
        source.process()
        
        mock_pad.set_caps.assert_called_once()
        caps_arg = mock_pad.set_caps.call_args[0][0]
        
        assert isinstance(caps_arg, Caps)
        assert "fingerprint" in caps_arg.params
        assert caps_arg.params["fingerprint"] == expected_hash
        
    finally:
        os.remove(tmp_path)

def test_mail_file_fingerprint(mock_pad):
    """Test that an EML file gets a SHA-256 fingerprint (which is the Message-ID)."""
    # Create a minimal valid EML
    content = (
        b"From: sender@example.com\n"
        b"To: recipient@example.com\n"
        b"Subject: Test Email\n"
        b"Message-ID: <unique-id-12345@example.com>\n"
        b"\n"
        b"This is the body of the email."
    )
    
    with tempfile.NamedTemporaryFile(suffix=".eml", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        uri = f"file://{tmp_path}"
        source = DiscreteDataSource(uri=uri)
        source._pads = [mock_pad]
        
        source.process()
        
        mock_pad.set_caps.assert_called_once()
        caps_arg = mock_pad.set_caps.call_args[0][0]
        
        # New Standard Name
        assert caps_arg.name == "message-rfc822"
        # The key change: Message-ID is now stored as "fingerprint"
        assert "fingerprint" in caps_arg.params
        assert caps_arg.params["fingerprint"] == "<unique-id-12345@example.com>"
        assert "message_id" not in caps_arg.params
        
    finally:
        os.remove(tmp_path)

def test_mbox_file_fingerprint(mock_pad):
    """Test that an MBOX file gets a SHA-256 fingerprint (NOT Message-ID)."""
    # Create a minimal MBOX (From line required)
    content = (
        b"From MAILER-DAEMON Fri Jul  8 12:08:34 2011\n"
        b"From: sender@example.com\n"
        b"To: recipient@example.com\n"
        b"Subject: Test Mbox Email\n"
        b"Message-ID: <first-msg-id@example.com>\n"
        b"\n"
        b"Body content."
    )
    expected_hash = hashlib.sha256(content).hexdigest()
    
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        uri = f"file://{tmp_path}"
        source = DiscreteDataSource(uri=uri)
        source._pads = [mock_pad]
        
        source.process()
        
        mock_pad.set_caps.assert_called_once()
        caps_arg = mock_pad.set_caps.call_args[0][0]
        
        # New Standard Name
        assert caps_arg.name == "application-mbox"
        assert "fingerprint" in caps_arg.params
        
        # KEY CHECK: Should be HASH, not the Message-ID
        assert caps_arg.params["fingerprint"] == expected_hash
        assert caps_arg.params["fingerprint"] != "<first-msg-id@example.com>"
        
    finally:
        os.remove(tmp_path)

def test_caps_params_refactor():
    """Verify Caps param refactor works mechanically."""
    c = Caps("test", "test-type", params={"foo": "bar", "list": [1, 2]})
    assert c.params["foo"] == "bar"
    
    c2 = c.merge_params({"baz": "qux"})
    assert c2.params["foo"] == "bar"
    assert c2.params["baz"] == "qux"
    # Original should be unchanged
    assert "baz" not in c.params


import os
import pytest
from unittest.mock import MagicMock
from cognita.source import DiscreteDataSource
from cognita.pad import Pad, PadDirection
from cognita.caps import Caps

@pytest.fixture
def mock_pad():
    pad = MagicMock(spec=Pad)
    pad.direction = PadDirection.SRC
    return pad

def test_mbox_source_caps(mock_pad):
    """Verify that an Mbox file source produces correct Caps.
    
    It should be detected as 'mail' but use a file fingerprint (SHA-256),
    not a Message-ID (which is for single-message files like EML).
    """
    # Use the fake data we generated
    mbox_path = os.path.abspath("tests/data/fake_mbox.dat")
    assert os.path.exists(mbox_path), "Test data missing: tests/data/fake_mbox.dat"
    
    uri = f"file://{mbox_path}"
    source = DiscreteDataSource(uri=uri)
    source._pads = [mock_pad]
    
    source.process()
    
    mock_pad.set_caps.assert_called_once()
    caps_arg = mock_pad.set_caps.call_args[0][0]
    
    # 1. Check basic type
    assert isinstance(caps_arg, Caps)
    assert caps_arg.name == "application-mbox"
    assert caps_arg.media_type == "application/mbox"
    
    # 2. Check extensions
    # Depending on detection, it might set extensions
    # type_finder: MBOX_CAPS has extensions=("mbox",)
    assert "extensions" in caps_arg.params
    assert "mbox" in caps_arg.params["extensions"]
    
    # 3. Check Identity
    # MUST have fingerprint
    assert "fingerprint" in caps_arg.params
    fp = caps_arg.params["fingerprint"]
    
    # MUST be SHA-256 (64 hex chars), NOT a Message-ID (<...>)
    assert len(fp) == 64
    assert not fp.startswith("<")
    assert "@" not in fp
    
    # MUST NOT have message_id param (legacy/EML only)
    assert "message_id" not in caps_arg.params

import os
import tempfile
from unittest.mock import MagicMock

import pytest

from cognita.caps import Caps
from cognita.mbox_parser import MboxParser
from cognita.pad import Pad, PadDirection


@pytest.fixture
def parser():
    return MboxParser()


def test_mbox_parser_flow(parser):
    """Test full flow: Input Mbox Caps -> Output enriched Caps + Messages."""

    # 0. Request Pads (Simulate link_many)
    src_pad = parser.request_pad(PadDirection.SRC, "src")
    sink_pad = parser.request_pad(PadDirection.SINK, "sink")

    # 1. Setup Mock Peer
    mock_sink_peer = MagicMock(spec=Pad)
    mock_sink_peer.element = MagicMock()
    src_pad.peer = mock_sink_peer

    # 2. Prepare fake Mbox
    content = (
        b"From MAILER-DAEMON Fri Jul  8 12:08:34 2011\n"
        b"Message-ID: <msg1@example.com>\n"
        b"\n"
        b"Body 1\n"
        b"\n"
        b"From MAILER-DAEMON Fri Jul  8 12:09:34 2011\n"
        b"Message-ID: <msg2@example.com>\n"
        b"\n"
        b"Body 2\n"
    )
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 3. Process
        caps = Caps("application/mbox", "application-mbox", params={"fingerprint": "hash123"})
        sink_pad.caps = caps

        parser.on_buffer(sink_pad, {"uri": f"file://{tmp_path}"})

        # 4. Verify Caps Propagation
        out_caps = src_pad.caps
        assert out_caps is not None
        assert out_caps.name == "application-mbox"
        assert out_caps.params["count"] == 2
        assert out_caps.params["fingerprint"] == "hash123"

        # 5. Verify Push
        # Should push 2 messages
        assert mock_sink_peer.element.on_buffer.call_count == 2

    finally:
        os.remove(tmp_path)


def test_reject_invalid_caps(parser):
    """Should ignore non-mbox caps."""
    src_pad = parser.request_pad(PadDirection.SRC)
    sink_pad = parser.request_pad(PadDirection.SINK)

    caps = Caps("other", "other")
    sink_pad.caps = caps

    # This should return early and print warning (no exception)
    parser.on_buffer(sink_pad, {"uri": "file://foo"})

    assert src_pad.caps is None

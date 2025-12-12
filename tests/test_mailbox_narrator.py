from unittest.mock import MagicMock, mock_open, patch

from cognita.caps import Caps
from cognita.mailbox_narrator import MailboxNarrator


def test_can_process_caps():
    narrator = MailboxNarrator()
    caps_mbox = Caps("application/mbox", "application-mbox")
    caps_eml = Caps("message/rfc822", "message-rfc822")
    caps_other = Caps("other", "other")

    assert narrator._can_process(caps_mbox, {"uri": "file://dummy"})
    assert narrator._can_process(caps_eml, {"uri": "file://dummy"})
    assert not narrator._can_process(caps_other, {"uri": "file://dummy"})


def test_can_process_uncapped_valid_header():
    narrator = MailboxNarrator()

    # Mock file content starting with "From "
    with (
        patch(
            "builtins.open", mock_open(read_data=b"From user@example.com Fri Jul 8 12:00:00 2011")
        ),
        patch("os.path.isfile", return_value=True),
    ):
        assert narrator._can_process(None, {"uri": "file://test.mbox"})


def test_can_process_uncapped_invalid_header():
    narrator = MailboxNarrator()

    # Mock random file content
    with (
        patch("builtins.open", mock_open(read_data=b"Not a mailbox file")),
        patch("os.path.isfile", return_value=True),
    ):
        assert not narrator._can_process(None, {"uri": "file://test.txt"})


def test_can_process_no_file():
    narrator = MailboxNarrator()

    with patch("os.path.isfile", return_value=False):
        assert not narrator._can_process(None, {"uri": "file://missing.mbox"})


def test_narrate_success():
    narrator = MailboxNarrator()

    # Mock mailbox
    mock_mbox_instance = MagicMock()
    # Mock messages
    msg1 = {"subject": "Hello", "from": "alice@example.com", "date": "2023-01-01"}
    msg2 = {"subject": "World", "from": "bob@example.com", "date": "2023-01-02"}
    mock_mbox_instance.__iter__.return_value = [msg1, msg2]
    mock_mbox_instance.__len__.return_value = 2

    with patch("mailbox.mbox", return_value=mock_mbox_instance):
        result = narrator._narrate({"uri": "file://test.mbox"}, None)

        assert "Mailbox: test.mbox" in result
        assert "containing 2 messages" in result
        assert "From: alice@example.com" in result
        assert "Subject: Hello" in result
        assert "From: bob@example.com" in result


def test_narrate_failure():
    narrator = MailboxNarrator()

    with patch("mailbox.mbox", side_effect=Exception("parse error")):
        result = narrator._narrate({"uri": "file://bad.mbox"}, None)
        assert "Failed to read mailbox: parse error" in result


def test_narrate_missing_uri():
    narrator = MailboxNarrator()
    assert narrator._narrate({}, None) is None

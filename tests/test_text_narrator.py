from unittest.mock import MagicMock, mock_open, patch

from cognita.caps import Caps
from cognita.ollama import OllamaError
from cognita.text_narrator import TextNarrator


def test_can_process_caps():
    narrator = TextNarrator()
    caps_text = Caps("text/plain", "plain-text")
    caps_doc = Caps("document", "document")
    caps_other = Caps("other", "other")

    assert narrator._can_process(caps_text, {})
    assert narrator._can_process(caps_doc, {})
    assert not narrator._can_process(caps_other, {})


def test_can_process_uncapped_extension():
    narrator = TextNarrator()
    # Check valid extensions
    assert narrator._can_process(None, {"uri": "file://test.txt"})
    assert narrator._can_process(None, {"uri": "readme.md"})
    assert narrator._can_process(None, {"uri": "data.csv"})
    assert narrator._can_process(None, {"uri": "log.json"})

    # Check invalid extensions
    assert not narrator._can_process(None, {"uri": "image.png"})
    assert not narrator._can_process(None, {"uri": "video.mp4"})

    # Check invalid payload
    assert not narrator._can_process(None, {"other": "data"})
    assert not narrator._can_process(None, None)


def test_narrate_with_preloaded_data():
    mock_client = MagicMock()
    mock_client._request.return_value = "- Entity A related to Entity B"
    narrator = TextNarrator(ollama_client=mock_client)

    payload = {"data": b"Hello world content", "uri": "file://test.txt"}
    result = narrator._narrate(payload, None)

    assert result == "- Entity A related to Entity B"
    mock_client._request.assert_called_once()
    args, _ = mock_client._request.call_args
    # Verify the prompt structure roughly
    assert "Hello world content" in args[0]
    assert "Analyze this text" in args[0]


def test_narrate_read_file_from_uri():
    mock_client = MagicMock()
    mock_client._request.return_value = "Summary"
    narrator = TextNarrator(ollama_client=mock_client)

    with (
        patch("builtins.open", mock_open(read_data="File content from disk")),
        patch("os.path.isfile", return_value=True),
    ):
        result = narrator._narrate({"uri": "file://disk.txt"}, None)

        assert result == "Summary"
        args, _ = mock_client._request.call_args
        assert "File content from disk" in args[0]


def test_narrate_no_client_fallback():
    narrator = TextNarrator(ollama_client=None)  # Creates default client
    narrator.ollama_client = None  # Force it to None for test
    payload = {"data": b"Short text", "uri": "test.txt"}
    result = narrator._narrate(payload, None)

    # Should perform fallback truncation
    assert "Short text..." in result
    assert "Text content" in result


def test_narrate_empty_or_missing():
    narrator = TextNarrator()

    # 1. Missing file
    with patch("os.path.isfile", return_value=False):
        result = narrator._narrate({"uri": "missing.txt"}, None)
        assert "Empty or unreadable" in result

    # 2. Empty data
    with (
        patch("builtins.open", mock_open(read_data="")),
        patch("os.path.isfile", return_value=True),
    ):
        result = narrator._narrate({"uri": "empty.txt"}, None)
        assert "Empty or unreadable" in result


def test_narrate_ollama_error_handling():
    mock_client = MagicMock()
    mock_client._request.side_effect = OllamaError("Unavailable")

    narrator = TextNarrator(ollama_client=mock_client)
    payload = {"data": b"content"}

    result = narrator._narrate(payload, None)
    assert "[ollama error] Unavailable" in result

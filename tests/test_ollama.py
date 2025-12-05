import json
from unittest.mock import MagicMock, patch
import pytest
from cognita.ollama import OllamaClient, OllamaError, OllamaUnavailableError, _extract_json_object
import urllib.error

def test_extract_json_object():
    assert _extract_json_object('{"key": "value"}') == {"key": "value"}
    assert _extract_json_object('prefix {"key": "value"} suffix') == {"key": "value"}
    assert _extract_json_object('invalid') is None
    assert _extract_json_object('{"incomplete"') is None

def test_ollama_request_success():
    client = OllamaClient()
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"response": "test response"}'
    mock_response.__enter__.return_value = mock_response
    
    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        result = client._request("prompt")
        assert result == "test response"
        mock_urlopen.assert_called_once()

def test_ollama_request_unavailable():
    client = OllamaClient()
    
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
        with pytest.raises(OllamaUnavailableError):
            client._request("prompt")

def test_ollama_request_error():
    client = OllamaClient()
    
    with patch("urllib.request.urlopen", side_effect=ValueError("some error")):
        with pytest.raises(OllamaError):
            client._request("prompt")

def test_guess_file_type_success():
    client = OllamaClient()
    
    json_response = {
        "mime_type": "text/plain",
        "type_name": "text",
        "rationale": "It looks like text",
        "extensions": ["txt"]
    }
    
    # Mock _request directly to avoid mocking urllib
    with patch.object(client, "_request", return_value=json.dumps(json_response)):
        caps = client.guess_file_type("file.txt", "HEADER", "Preview")
        
        assert caps.media_type == "text/plain"
        assert caps.name == "text"
        assert caps.description == "It looks like text"
        assert "txt" in caps.extensions

def test_guess_file_type_bad_json():
    client = OllamaClient()
    
    with patch.object(client, "_request", return_value="not json"):
        with pytest.raises(OllamaError, match="non-JSON answer"):
            client.guess_file_type("file.txt", "HEADER", "Preview")

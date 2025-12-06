from unittest.mock import MagicMock, patch, mock_open
import pytest
from cognita.image_narrator import ImageNarrator
from cognita.caps import Caps
from cognita.ollama import OllamaError

@pytest.fixture
def mock_ollama():
    client = MagicMock()
    client._request.return_value = "A beautiful sunset."
    return client

def test_image_narrator_init(mock_ollama):
    narrator = ImageNarrator(ollama_client=mock_ollama)
    assert narrator.ollama_client == mock_ollama
    
    # Test default client creation
    with patch("cognita.image_narrator.OllamaClient") as MockClient:
        ImageNarrator()
        MockClient.assert_called_with(model="qwen2.5vl:3b")

def test_can_process_caps():
    narrator = ImageNarrator()
    caps_image = Caps("image/jpeg", "image-photo")
    caps_other = Caps("text/plain", "text")
    
    assert narrator._can_process(caps_image, {})
    assert not narrator._can_process(caps_other, {})
    # The code allows uncapped processing if a URI is present, so this should match.
    assert narrator._can_process(None, {"uri": "file.jpg"})

def test_can_process_uncapped():
    narrator = ImageNarrator()
    assert narrator._can_process(None, {"uri": "file.jpg"})
    assert not narrator._can_process(None, {"other": "value"})

def test_narrate_success(mock_ollama):
    narrator = ImageNarrator(ollama_client=mock_ollama)
    
    with patch("builtins.open", mock_open(read_data=b"image data")), \
         patch("os.path.isfile", return_value=True):
        
        result = narrator._narrate({"uri": "test.jpg"}, None)
        assert result == "A beautiful sunset."
        mock_ollama._request.assert_called_once()
        args, kwargs = mock_ollama._request.call_args
        
        # Verify prompt structure
        assert "This image depicts" in args[0]
        assert "atomic statements" in args[0]
        assert "Base64 (entire image)" not in args[0] # Should NOT be in text
        
        # Verify image passed as argument
        assert "images" in kwargs
        assert kwargs["images"] == ["aW1hZ2UgZGF0YQ=="] # base64 of "image data"

def test_narrate_missing_file(mock_ollama):
    narrator = ImageNarrator(ollama_client=mock_ollama)
    
    with patch("os.path.isfile", return_value=False):
        result = narrator._narrate({"uri": "missing.jpg"}, None)
        assert result == "Image bytes unavailable; cannot generate description."
        mock_ollama._request.assert_not_called()

def test_narrate_ollama_error(mock_ollama):
    narrator = ImageNarrator(ollama_client=mock_ollama)
    mock_ollama._request.side_effect = OllamaError("Network error")
    
    with patch("builtins.open", mock_open(read_data=b"data")), \
         patch("os.path.isfile", return_value=True):
         
        result = narrator._narrate({"uri": "test.jpg"}, None)
        assert "[ollama error] Network error" in result

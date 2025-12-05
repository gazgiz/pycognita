from unittest.mock import MagicMock, patch, mock_open
import pytest
from cognita.source import PrebufferSource, DiscreteDataSource, TypeFinderError
from cognita.caps import Caps
from cognita.pad import PadDirection

@pytest.fixture
def mock_pad():
    pad = MagicMock()
    pad.direction = PadDirection.SRC
    return pad

def test_prebuffer_source_header_detect(mock_pad):
    source = PrebufferSource(uri="file://test.txt")
    source._pads = [mock_pad] # Inject mock pad
    
    mock_caps = Caps("text/plain", "text")
    source.header_analyzer = MagicMock()
    source.header_analyzer.detect.return_value = mock_caps
    
    with patch("builtins.open", mock_open(read_data=b"hello world")), \
         patch("os.path.isfile", return_value=True):
        
        source.process()
        
        mock_pad.set_caps.assert_called_with(mock_caps, propagate=True)
        mock_pad.push.assert_called_once()
        payload = mock_pad.push.call_args[0][0]
        assert payload["type_source"] == "header"
        assert payload["data"] == b"hello world"
        assert payload["uri"] == "file://test.txt"

def test_prebuffer_source_ollama_fallback(mock_pad):
    source = PrebufferSource(uri="file://unknown.bin")
    source._pads = [mock_pad]
    
    # Header detection fails
    source.header_analyzer = MagicMock()
    source.header_analyzer.detect.return_value = None
    
    # Ollama succeeds
    mock_caps = Caps("application/octet-stream", "binary")
    source.ollama_client = MagicMock()
    source.ollama_client.guess_file_type.return_value = mock_caps
    
    with patch("builtins.open", mock_open(read_data=b"unknown data")), \
         patch("os.path.isfile", return_value=True):
         
         source.process()
         
         mock_pad.set_caps.assert_called_with(mock_caps, propagate=True)
         payload = mock_pad.push.call_args[0][0]
         assert payload["type_source"] == "ollama"

def test_prebuffer_source_fail_no_ollama(mock_pad):
    source = PrebufferSource(uri="file://unknown.bin", ollama_client=None)
    source._pads = [mock_pad]
    
    source.header_analyzer = MagicMock()
    source.header_analyzer.detect.return_value = None
    
    with patch("builtins.open", mock_open(read_data=b"data")), \
         patch("os.path.isfile", return_value=True):
         
         with pytest.raises(TypeFinderError, match="Ollama fallback not configured"):
             source.process()

def test_prebuffer_source_ollama_error(mock_pad):
    source = PrebufferSource(uri="file://test.bin")
    source._pads = [mock_pad]
    
    source.header_analyzer = MagicMock()
    source.header_analyzer.detect.return_value = None
    
    source.ollama_client = MagicMock()
    source.ollama_client.guess_file_type.side_effect = Exception("error")
    
    with patch("builtins.open", mock_open(read_data=b"data")), \
         patch("os.path.isfile", return_value=True):
         
         with pytest.raises(TypeFinderError, match="Ollama error"):
             source.process()

def test_discrete_data_source(mock_pad):
    source = DiscreteDataSource(uri="file://test.file")
    source._pads = [mock_pad]
    
    source.process()
    
    mock_pad.push.assert_called_once()
    payload = mock_pad.push.call_args[0][0]
    assert payload["uri"] == "file://test.file"
    assert "data" not in payload # Discrete source doesn't read data

from unittest import mock
from unittest.mock import MagicMock, patch, mock_open
import pytest
from cognita.source import TimeSeriesDataSource, DiscreteDataSource, TypeFinderError
from cognita.caps import Caps
from cognita.pad import PadDirection

@pytest.fixture
def mock_pad():
    pad = MagicMock()
    pad.direction = PadDirection.SRC
    return pad

def test_timeseries_source_header_detect(mock_pad):
    source = TimeSeriesDataSource(uri="file://test.log")
    source._pads = [mock_pad]
    
    mock_caps = Caps("text/plain", "text")
    source.header_analyzer = MagicMock()
    source.header_analyzer.detect.return_value = mock_caps
    
    with patch("builtins.open", mock_open(read_data=b"log entry")), \
         patch("os.path.isfile", return_value=True):
        
        source.process()
        
        mock_pad.set_caps.assert_called_with(mock_caps, propagate=True)
        mock_pad.push.assert_called_once()
        payload = mock_pad.push.call_args[0][0]
        assert payload["type_source"] == "header"
        assert payload["data"] == b"log entry"
        assert payload["uri"] == "file://test.log"

def test_timeseries_source_ollama_fallback(mock_pad):
    source = TimeSeriesDataSource(uri="file://stream.bin")
    source._pads = [mock_pad]
    
    source.header_analyzer = MagicMock()
    source.header_analyzer.detect.return_value = None
    
    mock_caps = Caps("application/octet-stream", "binary")
    source.ollama_client = MagicMock()
    source.ollama_client.guess_file_type.return_value = mock_caps
    
    with patch("builtins.open", mock_open(read_data=b"stream data")), \
         patch("os.path.isfile", return_value=True):
         
         source.process()
         
         mock_pad.set_caps.assert_called_with(mock_caps, propagate=True)
         payload = mock_pad.push.call_args[0][0]
         assert payload["type_source"] == "ollama"
         assert payload["data"] == b"stream data"

def test_timeseries_source_fail_no_ollama(mock_pad):
    source = TimeSeriesDataSource(uri="file://u.bin", ollama_client=None)
    source._pads = [mock_pad]
    
    source.header_analyzer = MagicMock()
    source.header_analyzer.detect.return_value = None
    
    with patch("builtins.open", mock_open(read_data=b"data")), \
         patch("os.path.isfile", return_value=True):
         
         with pytest.raises(TypeFinderError, match="Ollama fallback not configured"):
             source.process()

def test_discrete_data_source(mock_pad):
    source = DiscreteDataSource(uri="file://test.file")
    source._pads = [mock_pad]
    
    mock_caps = Caps("text/plain", "text")
    source.header_analyzer = MagicMock()
    source.header_analyzer.detect.return_value = mock_caps
    
    with patch("builtins.open", mock_open(read_data=b"sample data")), \
         patch("os.path.isfile", return_value=True):
         
        source.process()
        
    # We use ANY for the caps argument because checking exact fingerprint hash here is brittle
    # and covered by test_identity.py
    mock_pad.set_caps.assert_called_with(mock.ANY, propagate=True)
    mock_pad.push.assert_called_once()
    payload = mock_pad.push.call_args[0][0]
    assert payload["uri"] == "file://test.file"
    assert payload["type_source"] == "header"
    assert "data" not in payload # Discrete source doesn't read data

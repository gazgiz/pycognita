import json
from unittest.mock import MagicMock

import pytest

from cognita.caps import Caps
from cognita.sink import SilentSink


def test_silent_sink_process():
    sink = SilentSink()
    assert sink.process() is None


def test_on_buffer_string():
    sink = SilentSink()
    pad = MagicMock()
    pad.caps = Caps("media/type", "test")

    sink.on_buffer(pad, "hello world")
    assert sink.output == "hello world"


def test_on_buffer_dict_description():
    sink = SilentSink()
    pad = MagicMock()
    pad.caps = Caps("media/type", "test")

    sink.on_buffer(pad, {"image_description": "desc", "other": "val"})
    assert sink.output == "desc"


def test_on_buffer_fallback_summary():
    sink = SilentSink()
    pad = MagicMock()
    caps = Caps("media/type", "test_name")
    pad.caps = caps

    sink.on_buffer(pad, {"other": "val"})

    # Should be JSON summary
    assert isinstance(sink.output, str)
    summary = json.loads(sink.output)
    assert summary["name"] == "test_name"


def test_on_buffer_missing_caps():
    sink = SilentSink()
    pad = MagicMock()
    pad.caps = None

    with pytest.raises(RuntimeError):
        sink.on_buffer(pad, "data")

"""# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial"""

from __future__ import annotations

from collections.abc import Iterable

from .element import Element
from .pad import PadDirection


class Pipeline:
    """Lightweight linear pipeline inspired by GStreamer's model.

    Elements are linked in order using dynamic pads. `run()` simply calls
    `process()` on each element (sources push buffers downstream inside
    `process`), then returns the final element's `output` for convenience.
    """

    def __init__(self, elements: Iterable[Element]):
        self.elements: list[Element] = list(elements)
        link_many(*self.elements)

    def run(self):
        """Execute each element in sequence; return the last element's output."""
        for element in self.elements:
            element.process()
        return getattr(self.elements[-1], "output", None) if self.elements else None


def link_many(*elements: Element) -> None:
    """Link a chain of elements using newly requested pads, like GStreamer's link_many.

    Each upstream element receives a new src pad that links to a new sink pad on
    the downstream element. No negotiation occurs here; caps are set by
    elements themselves when buffers flow.
    """
    if len(elements) < 2:
        return

    import itertools

    for upstream, downstream in itertools.pairwise(elements):
        src_pad = upstream.request_pad(PadDirection.SRC)
        sink_pad = downstream.request_pad(PadDirection.SINK)
        src_pad.link(sink_pad)

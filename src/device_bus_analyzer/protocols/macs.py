"""Electrolux/AEG MACS bus (tumble dryer) - placeholder.

The wire format is not documented here yet. Until findings exist the module keeps every burst as raw
data and reports no frames, so collecting and storing already work for MACS devices; decoding is added
once the protocol is understood (see docs/protocols/macs.md).
"""
from __future__ import annotations

from .bshdbus import BurstStats, Frame

NAME = "macs"
SPEC = "macs.yaml"


def parse_burst(data: bytes) -> tuple[list[Frame], BurstStats]:
    return [], BurstStats(rest=len(data))

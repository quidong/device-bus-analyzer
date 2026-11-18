"""Protocol modules. Each exposes `parse_burst(data) -> (frames, stats)` and a spec name."""
from . import bshdbus, macs

PROTOCOLS = {"bshdbus": bshdbus, "macs": macs}


def get(name: str):
    try:
        return PROTOCOLS[name]
    except KeyError:
        raise ValueError(f"unknown protocol {name!r}; known: {', '.join(PROTOCOLS)}") from None

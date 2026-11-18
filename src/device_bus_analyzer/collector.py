"""Read-only collector: subscribes to the ESPHome log stream over the native API and stores bus lines.

It never calls services, never writes entities and never sends anything to the device; the only API calls are
connect and subscribe_logs. Reconnects forever with back-off; every reconnect is logged so gaps are explainable.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

from .config import Device
from .store import Store

log = logging.getLogger("dba.collector")


def default_client_factory(dev: Device):
    import aioesphomeapi
    return aioesphomeapi.APIClient(dev.host, dev.port, None, noise_psk=dev.key)


class Collector:
    def __init__(self, store: Store, device: Device, client_factory: Callable[[Device], Any] = default_client_factory,
                 backoff: tuple[float, float] = (2.0, 60.0)):
        self.store, self.device, self.factory, self.backoff = store, device, client_factory, backoff
        self.source_id = store.source(device.name, device.protocol)
        self.lines = 0
        self.connected = False

    def on_log(self, msg: Any) -> None:
        text = msg.message.decode("utf-8", "replace") if isinstance(msg.message, (bytes, bytearray)) else str(msg.message)
        if self.store.ingest_line(self.source_id, text, time.time()):
            self.lines += 1

    async def run_once(self) -> None:
        client = self.factory(self.device)
        await client.connect(login=True)
        self.connected = True
        log.info("%s: connected", self.device.name)
        try:
            unsub = client.subscribe_logs(self.on_log, log_level=_debug_level())
            try:
                while True:
                    await asyncio.sleep(5)
                    if not getattr(client, "_connection", True):
                        break
            finally:
                if callable(unsub):
                    unsub()
        finally:
            self.connected = False
            await client.disconnect()

    async def run_forever(self, stop: asyncio.Event | None = None) -> None:
        delay = self.backoff[0]
        while not (stop and stop.is_set()):
            started = time.monotonic()
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:       # connection lost, device off (for example the dryer), auth failed ...
                log.warning("%s: connection ended: %s", self.device.name, exc)
            if time.monotonic() - started > 30:
                delay = self.backoff[0]
            try:
                await asyncio.wait_for(stop.wait(), delay) if stop else await asyncio.sleep(delay)
            except asyncio.TimeoutError:
                pass
            delay = min(delay * 2, self.backoff[1])


def _debug_level():
    from aioesphomeapi import LogLevel
    return LogLevel.LOG_LEVEL_INFO


async def run_all(store: Store, devices: list[Device]) -> None:
    await asyncio.gather(*(Collector(store, d).run_forever() for d in devices))

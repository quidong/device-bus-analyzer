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
        self.stopped = False            # set when the device is removed: late lines must not be stored

    def on_log(self, msg: Any) -> None:
        if self.stopped:
            return
        text = msg.message.decode("utf-8", "replace") if isinstance(msg.message, (bytes, bytearray)) else str(msg.message)
        if self.store.ingest_line(self.source_id, text, time.time()):
            self.lines += 1

    async def run_once(self) -> None:
        client = self.factory(self.device)
        await client.connect(login=True)
        self.connected = True
        log.info("%s: connected", self.device.name)
        self.store.touch_contact(self.source_id)
        try:
            unsub = client.subscribe_logs(self.on_log, log_level=_debug_level())
            try:
                while True:
                    await asyncio.sleep(5)
                    if not getattr(client, "_connection", True):
                        break
                    if not self.stopped:
                        self.store.touch_contact(self.source_id)        # connected = online, even when the bus is silent
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


class CollectorManager:
    """Keeps one collector task per enabled device stored in the database; ``sync()`` after every change of the device list.
    A changed connection (host, port, key) restarts only that device's collector; stored data is never touched."""

    def __init__(self, store: Store, factory: Callable[[Device], Any] = default_client_factory):
        self.store, self.factory = store, factory
        self.tasks: dict[str, tuple[Device, asyncio.Task, Collector]] = {}

    def sync(self) -> None:
        wanted = {d.name: d for d in self.store.connections()}
        for name, (dev, _task, _c) in list(self.tasks.items()):
            if wanted.get(name) != dev:
                self.stop_device(name)
        for name, dev in wanted.items():
            if name in self.tasks:
                continue
            try:                                   # one broken device entry must not stop the others
                c = Collector(self.store, dev, self.factory)
            except Exception as exc:
                log.error("device %s@%s:%s/%s not started: %s", dev.name, dev.host, dev.port, dev.protocol, exc)
                continue
            log.info("collecting %s from %s:%s (%s)", dev.name, dev.host, dev.port, dev.protocol)
            self.tasks[name] = (dev, asyncio.create_task(c.run_forever()), c)

    def stop_device(self, name: str) -> None:
        """Stop one collector for good (before its data is deleted): lines still in flight are dropped."""
        entry = self.tasks.pop(name, None)
        if entry:
            entry[2].stopped = True
            entry[1].cancel()

    def stop(self) -> None:
        for name in list(self.tasks):
            self.stop_device(name)


async def run_all(store: Store, devices: list[Device] | None = None) -> None:
    """Collector-only mode (``dba collect``): runs the devices stored in the database (the environment was imported before)."""
    if devices:
        store.seed_devices(devices)
    mgr = CollectorManager(store)
    mgr.sync()
    await asyncio.gather(*(v[1] for v in mgr.tasks.values()))

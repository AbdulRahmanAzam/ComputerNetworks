"""
A tiny unreliable channel connecting a sender (side A) and a
receiver (side B). It can drop, corrupt, and delay packets
independently in each direction.

Implementation notes:
- Two queues carry packets A->B and B->A.
- Each send() schedules the packet onto the destination queue after
  a random delay via threading.Timer so multiple in-flight packets
  can pass each other (which is important for GBN / SR testing).
- Loss and corruption are decided at send time using a seeded RNG
  so a given scenario can be reproduced.
"""

import queue
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Tuple

from packet import Packet


@dataclass
class ChannelConfig:
    loss_prob: float = 0.0
    corrupt_prob: float = 0.0
    delay_range: Tuple[float, float] = (0.0, 0.0)
    seed: int = 42


@dataclass
class ChannelStats:
    a_to_b_sent: int = 0
    a_to_b_dropped: int = 0
    a_to_b_corrupted: int = 0
    b_to_a_sent: int = 0
    b_to_a_dropped: int = 0
    b_to_a_corrupted: int = 0


class Channel:
    def __init__(self, config: ChannelConfig, logger=None):
        self.cfg = config
        self._rng = random.Random(config.seed)
        self._rng_lock = threading.Lock()
        self._ab: "queue.Queue[Packet]" = queue.Queue()
        self._ba: "queue.Queue[Packet]" = queue.Queue()
        self.stats = ChannelStats()
        self._log = logger if logger else (lambda *_: None)
        self._timers = []
        self._closed = False

    # --- helpers -----------------------------------------------------
    def _draw(self) -> Tuple[float, float, float]:
        with self._rng_lock:
            return (self._rng.random(),
                    self._rng.random(),
                    self._rng.uniform(*self.cfg.delay_range))

    def _deliver_later(self, q: "queue.Queue[Packet]", pkt: Packet, delay: float):
        if delay <= 0:
            q.put(pkt)
            return
        t = threading.Timer(delay, lambda: q.put(pkt) if not self._closed else None)
        t.daemon = True
        self._timers.append(t)
        t.start()

    def _schedule(self, direction: str, pkt: Packet):
        loss_roll, corrupt_roll, delay = self._draw()
        if direction == "ab":
            self.stats.a_to_b_sent += 1
            target = self._ab
        else:
            self.stats.b_to_a_sent += 1
            target = self._ba

        if loss_roll < self.cfg.loss_prob:
            if direction == "ab":
                self.stats.a_to_b_dropped += 1
            else:
                self.stats.b_to_a_dropped += 1
            self._log(f"[CHANNEL] DROPPED  {direction} {pkt.short()}")
            return

        if corrupt_roll < self.cfg.corrupt_prob:
            pkt = pkt.corrupted_copy()
            if direction == "ab":
                self.stats.a_to_b_corrupted += 1
            else:
                self.stats.b_to_a_corrupted += 1
            self._log(f"[CHANNEL] CORRUPT  {direction} {pkt.short()} (delay={delay:.2f}s)")
        else:
            self._log(f"[CHANNEL] deliver  {direction} {pkt.short()} (delay={delay:.2f}s)")

        self._deliver_later(target, pkt, delay)

    # --- public API --------------------------------------------------
    def send_ab(self, pkt: Packet):
        self._schedule("ab", pkt)

    def send_ba(self, pkt: Packet):
        self._schedule("ba", pkt)

    def recv_b(self, timeout=None) -> Packet:
        return self._ab.get(timeout=timeout)

    def recv_a(self, timeout=None) -> Packet:
        return self._ba.get(timeout=timeout)

    def close(self):
        self._closed = True
        for t in self._timers:
            try:
                t.cancel()
            except Exception:
                pass

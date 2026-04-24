"""
Shared helpers: a thread-safe logger with timestamps plus a few
small utilities. Kept separate so every protocol uses the same
log format in the console output.
"""

import threading
import time


class Logger:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._lock = threading.Lock()
        self._t0 = time.time()

    def __call__(self, msg: str):
        if not self.enabled:
            return
        with self._lock:
            print(f"[{time.time() - self._t0:6.2f}s] {msg}")


def chunk_payload(total_bytes: int, pkt_size: int):
    """Produce a list of packet-sized byte strings. The payload is a
    repeating pattern so a receiver can verify the final message."""
    data = bytearray()
    i = 0
    while len(data) < total_bytes:
        data.extend(f"[msg#{i:04d}]".encode())
        i += 1
    data = bytes(data[:total_bytes])
    return [data[i:i + pkt_size] for i in range(0, len(data), pkt_size)]

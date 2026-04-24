"""
Packet format used by all three protocols.

We keep a single dataclass for both data and ACK packets so the
unreliable channel does not need to know the protocol in use.
A very small "internet-style" 16-bit sum is used as the checksum so
the receiver can detect corruption that the channel injects.
"""

from dataclasses import dataclass, field


def _checksum(seq: int, is_ack: bool, data: bytes) -> int:
    # 16-bit additive checksum over (seq, flag, payload).
    total = (seq & 0xFFFF) + (1 if is_ack else 0)
    for b in data:
        total = (total + b) & 0xFFFF
    return total


@dataclass
class Packet:
    seq: int
    data: bytes = b""
    is_ack: bool = False
    checksum: int = 0
    # Set by the channel when it deliberately flips a bit so the
    # receiver's checksum test fails. We keep the original bytes as-is
    # and simply mark the packet as corrupted; this is cleaner than
    # randomly mutating data because the test results stay reproducible.
    _corrupted: bool = field(default=False, repr=False)

    @classmethod
    def make_data(cls, seq: int, data: bytes) -> "Packet":
        return cls(seq=seq, data=data, is_ack=False,
                   checksum=_checksum(seq, False, data))

    @classmethod
    def make_ack(cls, seq: int) -> "Packet":
        return cls(seq=seq, data=b"", is_ack=True,
                   checksum=_checksum(seq, True, b""))

    def is_corrupted(self) -> bool:
        if self._corrupted:
            return True
        return self.checksum != _checksum(self.seq, self.is_ack, self.data)

    def corrupted_copy(self) -> "Packet":
        # Return a shallow copy flagged as corrupted. The checksum
        # field stays intact so logs still show the "claimed" sum.
        return Packet(seq=self.seq, data=self.data, is_ack=self.is_ack,
                      checksum=self.checksum, _corrupted=True)

    def short(self) -> str:
        kind = "ACK" if self.is_ack else "DATA"
        tail = f" len={len(self.data)}" if not self.is_ack else ""
        return f"{kind}(seq={self.seq}{tail})"

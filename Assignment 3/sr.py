"""
Selective Repeat.

Sender:
- Window [base, base+N). Each un-acked packet has its own timer.
- An ACK marks that one packet as received; `base` slides forward
  through consecutive acked packets.
- On a per-packet timer expiry only that packet is retransmitted.

Receiver:
- Window [rcv_base, rcv_base+N). In-window packets are buffered and
  individually ACKed. When the packet at rcv_base is available the
  window slides and buffered consecutive packets are delivered.
- Packets whose seq falls inside the *previous* window are ACKed
  again (they are duplicates of already-delivered data) so the sender
  can stop retransmitting them.

Sequence space must be >= 2*N; we use exactly 2*N here.
"""

import queue
import time

from packet import Packet
from network import Channel


def _mod(window: int) -> int:
    # Textbook SR only needs 2*N, but in a simulator where packets can
    # be delayed further than the window slides, a tight 2*N modulus
    # lets a very late packet alias into a position of the *new* window.
    # Using 4*N keeps the sequence space unambiguous in that edge case.
    return max(4 * window, 8)


def sender(channel: Channel, messages, window: int, timeout: float,
           log=lambda *_: None, stats=None):
    mod = _mod(window)
    total = len(messages)
    base = 0
    next_seq = 0
    sent_pkts = {}   # abs -> Packet
    deadlines = {}   # abs -> deadline ts
    acked = set()
    retrans = 0

    while base < total:
        # Fill window.
        while next_seq < base + window and next_seq < total:
            pkt = Packet.make_data(next_seq % mod, messages[next_seq])
            sent_pkts[next_seq] = pkt
            deadlines[next_seq] = time.time() + timeout
            channel.send_ab(pkt)
            log(f"[SENDER]   send abs={next_seq} {pkt.short()} (window {base}..{base + window - 1})")
            next_seq += 1

        # Fire per-packet timers.
        now = time.time()
        for i in range(base, next_seq):
            if i in acked:
                continue
            if deadlines[i] <= now:
                channel.send_ab(sent_pkts[i])
                deadlines[i] = now + timeout
                retrans += 1
                log(f"[SENDER]   TIMEOUT abs={i} seq={i % mod} -> retransmit")

        # Compute the next event time.
        active = [deadlines[i] for i in range(base, next_seq) if i not in acked]
        wait = max(0.01, min(active) - time.time()) if active else timeout
        try:
            ack = channel.recv_a(timeout=wait)
        except queue.Empty:
            continue

        if ack.is_corrupted() or not ack.is_ack:
            log(f"[SENDER]   bad ACK ignored")
            continue

        # Map ACK seq back to an absolute index in [base, next_seq).
        hit = None
        for i in range(base, next_seq):
            if i in acked:
                continue
            if i % mod == ack.seq:
                hit = i
                break
        if hit is None:
            log(f"[SENDER]   stale/duplicate ACK{ack.seq} ignored")
            continue

        log(f"[SENDER]   ACK{ack.seq} -> abs={hit} acked")
        acked.add(hit)
        while base in acked:
            acked.discard(base)
            sent_pkts.pop(base, None)
            deadlines.pop(base, None)
            base += 1

    log(f"[SENDER]   done. retransmissions={retrans}")
    if stats is not None:
        stats["retransmissions"] = retrans


def receiver(channel: Channel, expected_count: int, delivered: list,
             window: int, log=lambda *_: None):
    mod = _mod(window)
    rcv_base = 0
    buffered = {}  # abs -> bytes

    def abs_in_window(seq_mod: int, base: int):
        for i in range(base, base + window):
            if i % mod == seq_mod:
                return i
        return None

    def abs_in_previous(seq_mod: int, base: int):
        start = max(0, base - window)
        for i in range(start, base):
            if i % mod == seq_mod:
                return i
        return None

    while len(delivered) < expected_count:
        pkt = channel.recv_b()
        if pkt.is_corrupted() or pkt.is_ack:
            log(f"[RECEIVER] bad pkt, silently dropped")
            continue

        idx = abs_in_window(pkt.seq, rcv_base)
        if idx is not None:
            channel.send_ba(Packet.make_ack(pkt.seq))
            if idx not in buffered and idx >= rcv_base:
                buffered[idx] = pkt.data
                log(f"[RECEIVER] buffered abs={idx} seq={pkt.seq} -> ACK{pkt.seq}")
            else:
                log(f"[RECEIVER] duplicate in-window seq={pkt.seq} -> ACK{pkt.seq}")
            while rcv_base in buffered:
                delivered.append(buffered.pop(rcv_base))
                log(f"[RECEIVER] delivered abs={rcv_base} ({len(delivered)}/{expected_count})")
                rcv_base += 1
            continue

        prev = abs_in_previous(pkt.seq, rcv_base)
        if prev is not None:
            log(f"[RECEIVER] old pkt seq={pkt.seq} -> re-ACK{pkt.seq}")
            channel.send_ba(Packet.make_ack(pkt.seq))
        else:
            log(f"[RECEIVER] seq={pkt.seq} far out of window, ignored")

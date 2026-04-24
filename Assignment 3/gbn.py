"""
Go-Back-N.

Key properties:
- Sender keeps a window [base, base + N).  `next_seq` is the next
  absolute index to transmit. Only a single retransmission timer is
  kept for the oldest un-acked packet.
- Receiver only accepts packets that match the next expected absolute
  sequence. Anything else is discarded and the last successful ACK is
  re-sent (cumulative ACK).

The sequence number modulus is max(2*N, 8). GBN actually only needs
> N but a little slack keeps log output readable.

Sender FSM (simplified)              Receiver FSM
  base..next_seq < base+N              expected := 0
  -------------------------            -------------------------
  send new pkt, start timer            pkt ok & seq == expected:
    if base == next_seq                  deliver, ACK(expected),
  timeout: resend all in window          expected += 1
  ACK(n): base := n + 1                else:
           restart/stop timer            resend last ACK
  corrupt ACK / dup: ignore
"""

import queue
import time

from packet import Packet
from network import Channel


def _pick_mod(window: int) -> int:
    m = 2 * window
    return m if m >= 8 else 8


def sender(channel: Channel, messages, window: int, timeout: float,
           log=lambda *_: None, stats=None):
    mod = _pick_mod(window)
    total = len(messages)
    base = 0
    next_seq = 0
    sent_pkts = {}      # absolute index -> Packet
    timer_start = None  # None when no timer is running
    retrans = 0

    def fire_timeout():
        nonlocal timer_start, retrans
        log(f"[SENDER]   TIMEOUT -> resend window [{base}..{next_seq - 1}]")
        for i in range(base, next_seq):
            channel.send_ab(sent_pkts[i])
            retrans += 1
        timer_start = time.time()

    while base < total:
        # 1) Fill the pipeline.
        while next_seq < base + window and next_seq < total:
            pkt = Packet.make_data(next_seq % mod, messages[next_seq])
            sent_pkts[next_seq] = pkt
            channel.send_ab(pkt)
            log(f"[SENDER]   send abs={next_seq} {pkt.short()} (window {base}..{base + window - 1})")
            if base == next_seq:
                timer_start = time.time()
            next_seq += 1

        # 2) Wait for an ACK but no longer than the timer allows.
        now = time.time()
        wait = timeout if timer_start is None else max(0.0, timer_start + timeout - now)
        try:
            ack = channel.recv_a(timeout=wait) if wait > 0 else None
        except queue.Empty:
            ack = None

        if ack is None:
            if timer_start is not None and time.time() - timer_start >= timeout:
                fire_timeout()
            continue

        if ack.is_corrupted() or not ack.is_ack:
            log(f"[SENDER]   bad ACK ignored")
            continue

        # Cumulative ACK: find the highest absolute index inside
        # [base, next_seq) whose seq-mod matches ack.seq.
        acked_abs = None
        for i in range(base, next_seq):
            if i % mod == ack.seq:
                acked_abs = i
        if acked_abs is None:
            log(f"[SENDER]   stale ACK{ack.seq} (outside window), ignoring")
            continue

        log(f"[SENDER]   ACK{ack.seq} -> base {base} => {acked_abs + 1}")
        for i in range(base, acked_abs + 1):
            sent_pkts.pop(i, None)
        base = acked_abs + 1
        if base == next_seq:
            timer_start = None
        else:
            timer_start = time.time()

    log(f"[SENDER]   done. retransmissions={retrans}")
    if stats is not None:
        stats["retransmissions"] = retrans


def receiver(channel: Channel, expected_count: int, delivered: list,
             window: int, log=lambda *_: None):
    mod = _pick_mod(window)
    expected = 0
    # "-1 mod" so the very first packet must be seq=0 or it is dropped.
    last_ack = (mod - 1)
    while len(delivered) < expected_count:
        pkt = channel.recv_b()
        if pkt.is_corrupted() or pkt.is_ack:
            log(f"[RECEIVER] bad pkt -> ACK{last_ack}")
            channel.send_ba(Packet.make_ack(last_ack))
            continue
        if pkt.seq == expected % mod:
            delivered.append(pkt.data)
            log(f"[RECEIVER] accepted abs={expected} seq={pkt.seq} -> ACK{pkt.seq}")
            channel.send_ba(Packet.make_ack(pkt.seq))
            last_ack = pkt.seq
            expected += 1
        else:
            log(f"[RECEIVER] out-of-order seq={pkt.seq} (wanted {expected % mod}) -> ACK{last_ack}")
            channel.send_ba(Packet.make_ack(last_ack))

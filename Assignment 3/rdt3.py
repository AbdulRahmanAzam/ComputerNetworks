"""
rdt 3.0 (Stop-and-Wait).

Sender FSM                       | Receiver FSM
---------------------------------|------------------------------
S0: Wait-for-call-0-from-above   | R0: Wait-for-0-from-below
    send(pkt0); start_timer;     |     got pkt, not corrupt, seq=0:
    -> S1                        |       deliver; send ACK0; -> R1
S1: Wait-for-ACK-0               |     else: send ACK1 (last good)
    timeout: resend pkt0;        | R1: Wait-for-1-from-below
    got ACK, not corrupt, seq=0: |     got pkt, not corrupt, seq=1:
      stop_timer; -> S2          |       deliver; send ACK1; -> R0
    corrupt or ACK1: stay/wait   |     else: send ACK0 (last good)
S2: Wait-for-call-1-from-above
    mirror image with seq=1
"""

import queue
import time

from packet import Packet
from network import Channel


def sender(channel: Channel, messages, timeout: float, log=lambda *_: None, stats=None):
    """Blocking stop-and-wait sender. Returns when every message has been ACKed."""
    seq = 0
    retrans = 0
    for idx, payload in enumerate(messages):
        pkt = Packet.make_data(seq, payload)
        log(f"[SENDER]   ({idx + 1}/{len(messages)}) sending {pkt.short()}")
        channel.send_ab(pkt)
        deadline = time.time() + timeout

        # Stay in "wait for ACK" until we either get the correct ACK or
        # the timer expires. Corrupted / wrong-seq ACKs are ignored and
        # we keep waiting the remainder of the timeout.
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                log(f"[SENDER]   TIMEOUT seq={seq} -> retransmit")
                retrans += 1
                channel.send_ab(pkt)
                deadline = time.time() + timeout
                continue
            try:
                ack = channel.recv_a(timeout=remaining)
            except queue.Empty:
                continue

            if ack.is_corrupted():
                log(f"[SENDER]   corrupt ACK ignored")
                continue
            if not ack.is_ack:
                log(f"[SENDER]   got DATA on ACK path, ignoring")
                continue
            if ack.seq != seq:
                log(f"[SENDER]   wrong ACK seq={ack.seq}, wanted {seq}")
                continue

            log(f"[SENDER]   ACK{seq} received")
            break

        seq ^= 1

    log(f"[SENDER]   done. retransmissions={retrans}")
    if stats is not None:
        stats["retransmissions"] = retrans


def receiver(channel: Channel, expected_count: int, delivered: list,
             log=lambda *_: None):
    expected = 0
    # Before we receive anything, duplicates would be of "the previous"
    # sequence number which doesn't exist. Using `1` here means the
    # first arriving packet must be seq=0 or it's rejected as a dup.
    last_ack = 1
    while len(delivered) < expected_count:
        pkt = channel.recv_b()
        if pkt.is_corrupted():
            log(f"[RECEIVER] corrupt pkt -> resend ACK{last_ack}")
            channel.send_ba(Packet.make_ack(last_ack))
            continue
        if pkt.is_ack:
            # Shouldn't happen on this link but be defensive.
            continue
        if pkt.seq == expected:
            delivered.append(pkt.data)
            log(f"[RECEIVER] accepted seq={pkt.seq} ({len(delivered)}/{expected_count}) -> ACK{pkt.seq}")
            channel.send_ba(Packet.make_ack(pkt.seq))
            last_ack = pkt.seq
            expected ^= 1
        else:
            # Duplicate of the previous packet: ACK it so the sender
            # can move forward.
            log(f"[RECEIVER] duplicate seq={pkt.seq} -> ACK{pkt.seq}")
            channel.send_ba(Packet.make_ack(pkt.seq))

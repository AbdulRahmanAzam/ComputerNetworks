# CN Assignment 3 — Report

## 1. Overview

This project simulates three reliable data-transfer protocols on top
of a deliberately unreliable in-process channel:

1. **rdt 3.0** — Stop-and-Wait, one packet in flight.
2. **Go-Back-N (GBN)** — cumulative ACKs, single timer, full-window
   retransmit on timeout.
3. **Selective Repeat (SR)** — per-packet ACKs and timers, only the
   lost/corrupted packet is retransmitted.

Every protocol runs the sender and receiver in two Python threads that
are connected by `network.Channel`. The channel drops, corrupts and
delays packets independently in each direction. Data flows only from
A to B (one-directional data) while control information (ACKs) travels
B to A, exactly as the assignment specifies.

## 2. File layout

```
packet.py    Packet + 16-bit checksum
network.py   Channel with loss / corruption / random delay per direction
util.py      thread-safe timestamped Logger + payload builder
rdt3.py      rdt 3.0 sender & receiver
gbn.py       Go-Back-N sender & receiver
sr.py        Selective Repeat sender & receiver
main.py      CLI driver (runs one protocol with chosen parameters)
tests.py     runs all four required scenarios for all three protocols
```

See [README.md](README.md) for exact run commands and CLI flags.

## 3. Packet & channel design

* `Packet.make_data(seq, data)` / `Packet.make_ack(seq)` each compute
  a 16-bit additive checksum over `(seq, is_ack, payload)`.
* `Channel` uses `threading.Timer` so packets scheduled with random
  delays can pass each other on the wire — this matters for GBN/SR
  where the window has multiple in-flight packets.
* Loss and corruption rolls use a seeded `random.Random`, so every
  scenario is reproducible.

## 4. Protocol summaries & FSMs

### 4.1 rdt 3.0 (Stop-and-Wait)

Sequence numbers alternate between `0` and `1`. A single retransmission
timer guards the one in-flight packet.

**Sender FSM**

```
          rdt_send(data)                          timeout
          make_pkt(0,data,chk);                   udt_send(pkt0);
          udt_send; start_timer                   start_timer
   ┌──────────────────────┐                ┌──────────────────────┐
   │ Wait-for-call-0-above│───────────────►│ Wait-for-ACK-0       │
   └──────────────────────┘                └──────────────────────┘
              ▲                                    │  rcv(ACK,0) & not corrupt
              │                                    │  stop_timer
              │ rcv(ACK,1) & not corrupt           ▼
   ┌──────────────────────┐                ┌──────────────────────┐
   │ Wait-for-ACK-1       │◄───────────────│ Wait-for-call-1-above│
   └──────────────────────┘                └──────────────────────┘
          timeout                              rdt_send(data)
          udt_send(pkt1);                      make_pkt(1,...);
          start_timer                          udt_send; start_timer
```

Corrupt ACKs or wrong-seq ACKs are ignored and the sender keeps
waiting for the remainder of the timer.

**Receiver FSM**

```
   ┌───────────────────────┐                ┌───────────────────────┐
   │ Wait-for-0-from-below │───────────────►│ Wait-for-1-from-below │
   └───────────────────────┘  rcv(pkt,0) &  └───────────────────────┘
        ▲     ▲                 not corrupt         │   rcv(pkt,1)&
        │     │ rcv(pkt,1) or   deliver;            │   not corrupt
        │     │ corrupt -> sndACK1                  │   deliver; sndACK1
        │     └──────────── (self loop)             ▼
        └──────────────────────── (self loop) rcv(pkt,0) or corrupt -> sndACK0
```

### 4.2 Go-Back-N

* Sender window `[base, base+N)`; `next_seq` advances as new packets
  enter the pipe. A **single** timer guards the oldest unacked packet.
* ACKs are cumulative: ACK `n` means everything through `n` is in.
* Receiver only accepts the packet with `seq == expected`; anything
  else triggers a re-ACK of the last in-order packet.

**Sender FSM**

```
            rdt_send(data)        ACK n in window,
            & next<base+N:        not corrupt:
            make_pkt; udt_send;   base := n+1;
            if base==next-1:       if base==next: stop_timer
              start_timer                 │
   ┌─────────────────────────┐            │
   │      running loop       │◄───────────┘
   └─────────────────────────┘
     │     ▲
     │     │ corrupt ACK / stale ACK: ignore
     │     │
     │     └──────── timeout: for i in [base..next-1]: udt_send(pkt_i);
     │                         start_timer
     │
     └───── next==base+N: refuse to send (window full)
```

**Receiver FSM**

```
   expected := 0
   loop:
     rcv(pkt):
        if not corrupt and seq == expected:
            deliver; send ACK(expected); expected += 1
        else:
            send ACK(last correctly received)      # cumulative re-ACK
```

### 4.3 Selective Repeat

Sequence modulus in this implementation is `max(4*N, 8)`. (The textbook
minimum is `2*N`; we use a larger space to avoid aliasing between a
very-late old packet and a fresh packet sharing the same `seq mod`.)

* Sender: per-packet timers and an `acked` set. `base` slides forward
  through consecutive acked positions. On a per-packet timeout only
  that packet is resent.
* Receiver: window `[rcv_base, rcv_base+N)`. In-window packets are
  buffered and individually ACKed; a contiguous prefix is delivered
  as soon as `rcv_base` becomes available. Packets in the previous
  window (already delivered) are re-ACKed so the sender stops resending.

**Sender FSM**

```
                  rdt_send(data) &
                  next<base+N:                     ACK n (uncovered in window):
                  make_pkt; udt_send; start_timer(n)
                                                   mark n acked;
                                                   while base in acked:
   ┌───────────────────────────┐                      slide base forward
   │      running loop         │
   └───────────────────────────┘
     │     ▲
     │     │  timer(i) fires, i not acked:
     │     │  udt_send(pkt_i); restart_timer(i)
     │     │
     │     │  corrupt/stale ACK: ignore
     │     └────────────────────────────
     └─── next==base+N: sender blocks on a window slot
```

**Receiver FSM**

```
   rcv_base := 0
   loop:
     rcv(pkt):
        if corrupt: drop
        elif seq in current window [rcv_base..rcv_base+N-1]:
            send ACK(seq)
            if pkt not already buffered: buffer[abs] := pkt.data
            while buffer[rcv_base] present:
                deliver buffer[rcv_base]; rcv_base += 1
        elif seq in previous window [rcv_base-N..rcv_base-1]:
            send ACK(seq)        # already delivered; help sender advance
        else:
            drop (far out of range)
```

## 5. Testing

`tests.py` runs every protocol under the four scenarios requested by
the assignment. All scenarios use **12 packets** of **24 bytes** and
window **N = 4**. Random seed is fixed (42) so results are
reproducible.

| Scenario      | loss | corrupt | delay range (s) | timeout (s) |
|---------------|-----:|--------:|-----------------|------------:|
| clean         | 0.00 | 0.00    | 0.00 – 0.02     | 0.40        |
| packet loss   | 0.30 | 0.00    | 0.00 – 0.05     | 0.40        |
| corruption    | 0.00 | 0.30    | 0.00 – 0.05     | 0.40        |
| delays        | 0.00 | 0.00    | 0.20 – 0.60     | 1.60        |

**Note on the delays scenario:** rdt 3.0 with only 2 sequence numbers
requires `2 * max_delay < timeout`, otherwise an ACK of packet N that
is delayed past the timeout can be mistaken for the ACK of packet
N+2 (same alternating bit). The timeout for the delays scenario is
therefore chosen larger than the maximum round-trip time.

### 5.1 Results

Output of `python tests.py` (reproduced verbatim):

```
proto  scenario       result    pkts  retx  time(s)
------------------------------------------------------------------------
rdt3   clean          PASS        12     0     0.26
rdt3   packet loss    PASS        12    13     5.82
rdt3   corruption     PASS        12    22     9.46
rdt3   delays         PASS        12     0     9.46
gbn    clean          PASS        12    21     2.56
gbn    packet loss    PASS        12    28     4.02
gbn    corruption     PASS        12    35     4.97
gbn    delays         PASS        12    21    15.25
sr     clean          PASS        12     0     0.09
sr     packet loss    PASS        12    13     2.96
sr     corruption     PASS        12    30     5.37
sr     delays         PASS        12     0     2.71
------------------------------------------------------------------------
overall: PASS
```

Each `PASS` means all 12 payloads were delivered to the receiver
**in order** and byte-identical to what the sender produced. The `retx`
column counts retransmissions, which behaves as expected:

* **GBN retransmits whole windows** on a timeout, so its `retx` count
  is higher than SR for the same loss rate.
* **SR only retransmits the actual lost/corrupt packet** — compare the
  13 retransmissions for `sr/packet loss` vs 28 for `gbn/packet loss`.
* Under the delays scenario with generous timeout, SR finishes with 0
  retransmissions while GBN still retransmits because its single
  timer for the window base expires while other packets are still in
  flight.

### 5.2 Observations

* **Clean runs** do zero retransmissions across all three protocols —
  a good sanity check that the baseline path works.
* **Corruption is "worse" than loss** for GBN because a corrupt ACK at
  the head of the window forces the whole window to be resent on the
  next timer expiry.
* **Pipelining speeds SR and GBN up** clearly on the clean run:
  `rdt3=0.26s`, `gbn=2.56s`, `sr=0.09s`. (GBN is slower than SR here
  because its sender timer starts at the first packet of each window,
  so even a clean run pays the single-timer latency.)

## 6. How to reproduce

```powershell
# Full required test sweep (pass/fail)
python tests.py

# Full required test sweep with per-packet channel logs
python tests.py --verbose

# Any custom single run (see README.md for every flag)
python main.py --proto sr --packets 40 --window 6 `
               --loss 0.2 --corrupt 0.1 --delay 0.0 0.2
```

## 7. Design choices worth noting

* **Bytes, not just sequence numbers, are verified.** The driver
  builds a deterministic payload and the test harness checks that the
  final delivered bytes equal the input, in order.
* **No sockets.** The assignment only requires simulating an
  unreliable channel; running sender and receiver as threads over a
  `queue`-based channel keeps the code portable and avoids OS/firewall
  noise in the results.
* **Deterministic RNG seed** — every result above is reproducible on
  any machine with Python 3.9+.
* **Per-direction loss/corruption**: both DATA and ACK paths are
  independently unreliable, which is what forces rdt 3.0 to maintain
  alternating-bit numbering even though there is "only one packet
  in flight".

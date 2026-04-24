# CN Assignment 3 — rdt 3.0, Go-Back-N, Selective Repeat

A from-scratch Python simulation of three reliable data-transfer
protocols over a deliberately unreliable in-process "network".


# Demo Video:  https://www.youtube.com/watch?v=GFaueHVGxUE

## Files

| File         | Purpose |
|--------------|---------|
| `packet.py`  | Packet dataclass + 16-bit checksum |
| `network.py` | Unreliable `Channel` (loss, corruption, random delays) |
| `util.py`    | Thread-safe timestamped logger + payload helper |
| `rdt3.py`    | rdt 3.0 sender and receiver |
| `gbn.py`     | Go-Back-N sender and receiver |
| `sr.py`      | Selective Repeat sender and receiver |
| `main.py`    | CLI driver for a single protocol/scenario |
| `tests.py`   | Runs all four required scenarios against every protocol |
| `REPORT.md`  | Design notes, FSMs, and test results |

## Requirements

Python 3.9+ (standard library only, no pip installs).

## Running

Run all required scenarios for every protocol and print a pass/fail
summary:

```powershell
python tests.py            # summary only
python tests.py --verbose  # also stream the per-packet logs
```

Run a single configuration of your choice:

```powershell
# rdt 3.0 with 20 packets of 32 bytes, 10% loss, 10% corruption
python main.py --proto rdt3 --packets 20 --size 32 `
               --loss 0.1 --corrupt 0.1

# Go-Back-N with window=5
python main.py --proto gbn --packets 30 --window 5 `
               --loss 0.2 --delay 0.0 0.1

# Selective Repeat
python main.py --proto sr  --packets 30 --window 5 `
               --corrupt 0.2 --delay 0.0 0.2
```

All parameters:

```
--proto   rdt3 | gbn | sr         (required)
--packets INT    number of data packets      (default 10)
--size    INT    bytes per packet            (default 16)
--window  INT    window N for GBN / SR       (default 4)
--timeout FLOAT  retransmission timeout (s)  (default 0.6)
--loss    FLOAT  per-direction loss prob     (default 0.0)
--corrupt FLOAT  per-direction corrupt prob  (default 0.0)
--delay   MIN MAX random delay range (s)     (default 0.0 0.05)
--seed    INT    RNG seed for reproducibility (default 42)
--quiet          suppress per-packet logging
```

The exit code is `0` when every packet arrives in order with correct
bytes, otherwise `1`.

## What you will see

For each scenario `tests.py` prints the channel/sender/receiver
activity (timestamp prefixed) and a final summary, e.g.:

```
proto  scenario       result    pkts  retx  time(s)
------------------------------------------------------------------------
rdt3   clean          PASS        12     0     0.26
rdt3   packet loss    PASS        12    13     5.82
...
sr     delays         PASS        12     0     2.71
------------------------------------------------------------------------
overall: PASS
```

"""
Runs the four required testing scenarios against all three protocols
and prints a compact pass/fail table at the end.

Scenarios (per the assignment):
    1. No packet loss or corruption
    2. Packet loss
    3. Packet corruption
    4. Delayed packets

Use `python tests.py` to run the full sweep.
Pass `--verbose` to also stream the per-packet logs.
"""

import argparse

from main import run


SCENARIOS = [
    # (name, loss, corrupt, delay_min, delay_max, timeout)
    ("clean",        0.00, 0.00, 0.00, 0.02, 0.40),
    ("packet loss",  0.30, 0.00, 0.00, 0.05, 0.40),
    ("corruption",   0.00, 0.30, 0.00, 0.05, 0.40),
    # Delay scenario: pick delays so that a round trip can still fit
    # inside the timeout (2*max_delay < timeout). This is required for
    # rdt 3.0 to work correctly with only 2 sequence numbers; otherwise
    # a delayed ACK of packet N can be confused with an ACK of N+2.
    ("delays",       0.00, 0.00, 0.20, 0.60, 1.60),
]

PROTOS = ["rdt3", "gbn", "sr"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--packets", type=int, default=12)
    ap.add_argument("--size", type=int, default=24)
    ap.add_argument("--window", type=int, default=4)
    args = ap.parse_args()

    rows = []
    for proto in PROTOS:
        for name, loss, corr, dmin, dmax, timeout in SCENARIOS:
            print("\n" + "#" * 72)
            print(f"# {proto.upper()}  /  scenario: {name}")
            print("#" * 72)
            res = run(proto, args.packets, args.size, args.window,
                      timeout, loss, corr, dmin, dmax,
                      seed=42, quiet=not args.verbose)
            rows.append((proto, name, res))

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"{'proto':<6} {'scenario':<14} {'result':<8} "
          f"{'pkts':>5} {'retx':>5} {'time(s)':>8}")
    print("-" * 72)
    all_ok = True
    for proto, name, r in rows:
        ok = "PASS" if r["ok"] else "FAIL"
        all_ok &= r["ok"]
        print(f"{proto:<6} {name:<14} {ok:<8} "
              f"{r['delivered']:>5} {r['retransmissions']:>5} "
              f"{r['time']:>8.2f}")
    print("-" * 72)
    print("overall:", "PASS" if all_ok else "FAIL")
    raise SystemExit(0 if all_ok else 1)


if __name__ == "__main__":
    main()

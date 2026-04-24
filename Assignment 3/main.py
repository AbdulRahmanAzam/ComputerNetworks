"""
Command-line driver.

Run a single protocol with a chosen network profile. Examples:

    python main.py --proto rdt3 --packets 8 --size 16
    python main.py --proto gbn  --packets 20 --size 32 --window 4 \
                   --loss 0.2 --corrupt 0.1 --delay 0.0 0.3
    python main.py --proto sr   --packets 20 --window 4 --loss 0.2

The sender and receiver run in separate threads connected by the
Channel object. Because control information flows both ways (DATA
from A to B and ACKs from B to A) the simulation is uni-directional
for data even though ACKs travel back.
"""

import argparse
import threading
import time

import rdt3
import gbn
import sr
from network import Channel, ChannelConfig
from util import Logger, chunk_payload


PROTOCOLS = {
    "rdt3": ("rdt 3.0 (Stop-and-Wait)", rdt3),
    "gbn":  ("Go-Back-N", gbn),
    "sr":   ("Selective Repeat", sr),
}


def run(proto: str, n_packets: int, pkt_size: int, window: int,
        timeout: float, loss: float, corrupt: float,
        delay_min: float, delay_max: float, seed: int,
        quiet: bool = False):
    name, module = PROTOCOLS[proto]
    log = Logger(enabled=not quiet)

    payload_bytes = n_packets * pkt_size
    messages = chunk_payload(payload_bytes, pkt_size)
    assert len(messages) == n_packets

    cfg = ChannelConfig(loss_prob=loss, corrupt_prob=corrupt,
                        delay_range=(delay_min, delay_max), seed=seed)
    channel = Channel(cfg, logger=log)

    log(f"=== {name} | packets={n_packets} size={pkt_size}B "
        f"window={window} timeout={timeout}s loss={loss} "
        f"corrupt={corrupt} delay={delay_min}..{delay_max}s seed={seed} ===")

    delivered: list = []
    stats = {"retransmissions": 0}

    if proto == "rdt3":
        t_send = threading.Thread(
            target=module.sender,
            args=(channel, messages, timeout),
            kwargs={"log": log, "stats": stats}, daemon=True)
        t_recv = threading.Thread(
            target=module.receiver,
            args=(channel, n_packets, delivered),
            kwargs={"log": log}, daemon=True)
    else:
        t_send = threading.Thread(
            target=module.sender,
            args=(channel, messages, window, timeout),
            kwargs={"log": log, "stats": stats}, daemon=True)
        t_recv = threading.Thread(
            target=module.receiver,
            args=(channel, n_packets, delivered, window),
            kwargs={"log": log}, daemon=True)

    start = time.time()
    t_recv.start()
    t_send.start()
    t_send.join(timeout=60)
    t_recv.join(timeout=5)
    elapsed = time.time() - start
    channel.close()

    ok = (len(delivered) == n_packets and
          all(delivered[i] == messages[i] for i in range(n_packets)))

    log(f"=== result: {'OK' if ok else 'FAILED'} "
        f"delivered {len(delivered)}/{n_packets} "
        f"retransmissions={stats['retransmissions']} "
        f"time={elapsed:.2f}s ===")
    log(f"    channel: A->B sent={channel.stats.a_to_b_sent} "
        f"drop={channel.stats.a_to_b_dropped} "
        f"corrupt={channel.stats.a_to_b_corrupted}; "
        f"B->A sent={channel.stats.b_to_a_sent} "
        f"drop={channel.stats.b_to_a_dropped} "
        f"corrupt={channel.stats.b_to_a_corrupted}")

    return {
        "ok": ok,
        "delivered": len(delivered),
        "expected": n_packets,
        "retransmissions": stats["retransmissions"],
        "time": elapsed,
        "channel_stats": channel.stats,
    }


def build_parser():
    p = argparse.ArgumentParser(description="rdt3 / GBN / SR simulator")
    p.add_argument("--proto", choices=PROTOCOLS.keys(), required=True)
    p.add_argument("--packets", type=int, default=10)
    p.add_argument("--size", type=int, default=16, help="payload bytes per packet")
    p.add_argument("--window", type=int, default=4, help="window N for GBN/SR")
    p.add_argument("--timeout", type=float, default=0.6)
    p.add_argument("--loss", type=float, default=0.0)
    p.add_argument("--corrupt", type=float, default=0.0)
    p.add_argument("--delay", type=float, nargs=2, default=[0.0, 0.05],
                   metavar=("MIN", "MAX"))
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--quiet", action="store_true")
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    res = run(args.proto, args.packets, args.size, args.window,
              args.timeout, args.loss, args.corrupt,
              args.delay[0], args.delay[1], args.seed, args.quiet)
    raise SystemExit(0 if res["ok"] else 1)

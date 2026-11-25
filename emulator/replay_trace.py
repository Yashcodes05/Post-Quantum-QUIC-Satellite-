"""
Dynamic Linux tc/netem trace replayer for LEO satellite (Starlink) link emulation.
Applies time-varying RTT, jitter, and burst packet loss from a CSV trace file
onto a Linux network interface using `tc qdisc replace ... netem`.
"""

import argparse
import csv
import subprocess
import time
from pathlib import Path
from typing import Dict, List


def load_trace(trace_path: Path) -> List[Dict[str, float]]:
    """Load a CSV trace with columns: time_s, rtt_ms, jitter_ms, loss_pct, is_handover."""
    rows: List[Dict[str, float]] = []
    with trace_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "time_s": float(row["time_s"]),
                "rtt_ms": float(row["rtt_ms"]),
                "jitter_ms": float(row["jitter_ms"]),
                "loss_pct": float(row["loss_pct"]),
                "is_handover": int(row["is_handover"]),
            })
    return rows


def apply_netem(iface: str, rtt_ms: float, jitter_ms: float, loss_pct: float, dry_run: bool) -> None:
    """Apply netem delay and packet loss to the target interface."""
    one_way_ms = max(0.5, rtt_ms / 2.0)
    cmd = [
        "tc", "qdisc", "replace", "dev", iface, "root", "netem",
        "delay", f"{one_way_ms:.2f}ms", f"{jitter_ms:.2f}ms",
        "loss", f"{loss_pct:.2f}%",
    ]
    if dry_run:
        return
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def replay_loop(trace: List[Dict[str, float]], iface: str, loop: bool, dry_run: bool, max_steps: int = 0) -> None:
    """Replay the trace in real time (or fast dry-run) updating netem at each step."""
    iteration = 0
    while True:
        iteration += 1
        start_wall = time.monotonic()
        for idx, sample in enumerate(trace):
            if max_steps and idx >= max_steps:
                break
            target_t = sample["time_s"]
            if not dry_run:
                now_elapsed = time.monotonic() - start_wall
                if target_t > now_elapsed:
                    time.sleep(target_t - now_elapsed)
            apply_netem(iface, sample["rtt_ms"], sample["jitter_ms"], sample["loss_pct"], dry_run)
            if sample["is_handover"] == 1 or idx % 50 == 0:
                tag = "HANDOVER" if sample["is_handover"] == 1 else "NORMAL  "
                print(
                    f"[iter={iteration} t={sample['time_s']:5.1f}s {tag}] "
                    f"iface={iface} rtt={sample['rtt_ms']:6.1f}ms "
                    f"jitter={sample['jitter_ms']:4.1f}ms loss={sample['loss_pct']:5.2f}%"
                )
        if not loop:
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay LEO Starlink traces onto Linux tc/netem.")
    parser.add_argument("--trace", type=Path, required=True, help="Path to CSV trace file.")
    parser.add_argument("--iface", type=str, default="eth0", help="Network interface for tc netem.")
    parser.add_argument("--loop", action="store_true", help="Loop trace continuously.")
    parser.add_argument("--dry-run", action="store_true", help="Print updates without invoking tc.")
    parser.add_argument("--max-steps", type=int, default=0, help="Optional limit on steps (0 = all).")
    args = parser.parse_args()

    trace = load_trace(args.trace)
    print(f"Loaded {len(trace)} trace samples from {args.trace} (dry_run={args.dry_run}).")
    replay_loop(trace, args.iface, args.loop, args.dry_run, args.max_steps)


if __name__ == "__main__":
    main()

"""
Generates realistic 60-second Starlink LEO and Terrestrial baseline CSV traces
at 100ms resolution for tc/netem replay and QUIC handshake simulation.

Starlink handover marks occur every 15s at 12s, 27s, 42s, and 57s of each minute.
"""

import csv
import math
import random
from pathlib import Path

HANDOVER_MARKS = (12.0, 27.0, 42.0, 57.0)


def generate_starlink_trace(out_path: Path, duration_s: float = 60.0, step_s: float = 0.1, seed: int = 42) -> None:
    rng = random.Random(seed)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    steps = int(round(duration_s / step_s))

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time_s", "rtt_ms", "jitter_ms", "loss_pct", "is_handover"])

        for i in range(steps):
            t = round(i * step_s, 2)
            # Slow orbital RTT drift (38ms - 52ms)
            base_rtt = 44.0 + 6.0 * math.sin(2 * math.pi * t / 30.0) + rng.gauss(0, 1.8)
            jitter = max(1.5, 4.0 + rng.gauss(0, 1.0))
            loss_pct = max(0.1, 0.6 + rng.gauss(0, 0.25))
            is_handover = 0

            for mark in HANDOVER_MARKS:
                dt = t - mark
                if -0.05 <= dt <= 0.45:
                    is_handover = 1
                    # Peak spike at +0.1s..+0.25s after handover mark
                    intensity = math.exp(-((dt - 0.15) ** 2) / 0.04)
                    base_rtt += 140.0 * intensity + rng.uniform(20.0, 55.0)
                    jitter += 35.0 * intensity
                    loss_pct = min(42.0, 14.0 + 22.0 * intensity + rng.uniform(0.0, 6.0))
                    break

            writer.writerow([
                f"{t:.1f}",
                f"{max(20.0, base_rtt):.2f}",
                f"{jitter:.2f}",
                f"{loss_pct:.2f}",
                is_handover,
            ])


def generate_terrestrial_trace(out_path: Path, duration_s: float = 60.0, step_s: float = 0.1, seed: int = 99) -> None:
    rng = random.Random(seed)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    steps = int(round(duration_s / step_s))

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time_s", "rtt_ms", "jitter_ms", "loss_pct", "is_handover"])

        for i in range(steps):
            t = round(i * step_s, 2)
            rtt = max(8.0, 18.0 + rng.gauss(0, 1.2))
            jitter = max(0.3, 1.2 + rng.gauss(0, 0.3))
            loss_pct = max(0.05, 0.2 + rng.gauss(0, 0.08))
            writer.writerow([f"{t:.1f}", f"{rtt:.2f}", f"{jitter:.2f}", f"{loss_pct:.2f}", 0])


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent / "traces"
    generate_starlink_trace(root / "starlink_15s_trace.csv")
    generate_terrestrial_trace(root / "terrestrial_trace.csv")
    print(f"Generated traces in {root}")

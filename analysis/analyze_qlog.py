"""
CLI analyzer for benchmark_results.json and qlog event traces.
Prints ACN transport-layer metrics (handshake latency, failure rate, PTO fires,
and 3x anti-amplification blocking) to the terminal.
"""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze PQ-QUIC LEO benchmark JSON.")
    parser.add_argument("json_path", type=Path, help="Path to benchmark_results.json")
    args = parser.parse_args()

    with args.json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    print("=== RQ2: Algorithm & Anti-Amplification Matrix (LEO vs Terrestrial) ===")
    print(f"{'Profile':<24} {'Env':<14} {'Pkts(C/S)':<11} {'Mean(ms)':<10} {'P95(ms)':<10} {'Fail%':<8} {'3xBlock%':<9} {'PTOs':<6}")
    print("-" * 96)
    for row in data.get("rq2_algorithm_matrix", []):
        pkts = f"{row['client_packets']}/{row['server_packets']}"
        print(
            f"{row['profile']:<24} {row['environment']:<14} {pkts:<11} "
            f"{row['mean_ms']:<10.1f} {row['p95_ms']:<10.1f} "
            f"{row['failure_rate_pct']:<8.1f} {row['amplification_blocked_pct']:<9.1f} {row['mean_pto_fires']:<6.2f}"
        )

    print("\n=== RQ3 & RQ4: Handover-Aware Scheme & Mitigations (Kyber768+Dilithium3 @ Handover) ===")
    print(f"{'Mitigation':<28} {'Mean(ms)':<10} {'TTFB(ms)':<10} {'Fail%':<8} {'PTOs':<6} {'Defer(ms)':<10}")
    print("-" * 76)
    for row in data.get("rq3_rq4_mitigations", []):
        if row["profile"] == "Kyber768+Dilithium3":
            print(
                f"{row['mitigation_label']:<28} {row['mean_ms']:<10.1f} {row['mean_ttfb_ms']:<10.1f} "
                f"{row['failure_rate_pct']:<8.1f} {row['mean_pto_fires']:<6.2f} {row['mean_defer_ms']:<10.1f}"
            )


if __name__ == "__main__":
    main()

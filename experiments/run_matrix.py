"""
Runs the full RQ1-RQ4 experiment matrix for Post-Quantum QUIC over LEO links
and exports structured JSON results for the GitHub Pages interactive analyzer.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from emulator.replay_trace import load_trace
from experiments.quic_transport_sim import PROFILES, simulate_handshake


def summarize_runs(results) -> Dict:
    times = [r.completion_time_ms for r in results]
    ttfbs = [r.ttfb_ms for r in results]
    failures = sum(1 for r in results if r.failed)
    return {
        "n_runs": len(results),
        "mean_ms": round(statistics.mean(times), 2),
        "median_ms": round(statistics.median(times), 2),
        "p95_ms": round(sorted(times)[max(0, int(0.95 * len(times)) - 1)], 2),
        "mean_ttfb_ms": round(statistics.mean(ttfbs), 2),
        "failure_rate_pct": round((failures / len(results)) * 100.0, 2),
        "mean_rtts": round(statistics.mean(r.rtts for r in results), 2),
        "mean_packets": round(statistics.mean(r.total_packets for r in results), 2),
        "mean_pto_fires": round(statistics.mean(r.pto_fires for r in results), 2),
        "amplification_blocked_pct": round(
            (sum(1 for r in results if r.amplification_blocked) / len(results)) * 100.0, 2
        ),
        "mean_defer_ms": round(statistics.mean(r.defer_ms for r in results), 2),
    }


def run_all(starlink_trace_path: Path, terrestrial_trace_path: Path, output_path: Path, trials: int = 30) -> Dict:
    starlink = load_trace(starlink_trace_path)
    terrestrial = load_trace(terrestrial_trace_path)

    # RQ1: Handover Cycle Sweep around the 12.0s handover mark (offsets -2.0s to +2.0s)
    offsets = [-2.0, -1.0, -0.5, -0.25, 0.0, 0.15, 0.3, 0.5, 1.0, 2.0]
    rq1_profiles = ["X25519+RSA2048", "P256_Kyber768+RSA2048", "Kyber768+Dilithium3", "Kyber768+SPHINCS+"]
    rq1_sweep = []

    for prof in rq1_profiles:
        for scheme in ("unmodified", "handover_aware"):
            series = []
            for off in offsets:
                t_start = 12.0 + off
                runs = [
                    simulate_handshake(starlink, prof, t_start, scheme=scheme, seed=1000 + i)
                    for i in range(trials)
                ]
                s = summarize_runs(runs)
                s["offset_s"] = off
                series.append(s)
            rq1_sweep.append({"profile": prof, "scheme": scheme, "points": series})

    # RQ2: Algorithm & Anti-Amplification Matrix (LEO vs Terrestrial, random start times across 60s)
    rq2_matrix = []
    for prof_name, prof_obj in PROFILES.items():
        for env_name, trace in (("LEO_Starlink", starlink), ("Terrestrial", terrestrial)):
            runs = [
                simulate_handshake(
                    trace,
                    prof_name,
                    start_time_s=(i * 1.9) % 58.0,
                    scheme="unmodified",
                    seed=2000 + i,
                )
                for i in range(trials * 2)
            ]
            summary = summarize_runs(runs)
            rq2_matrix.append({
                "profile": prof_name,
                "category": prof_obj.category,
                "environment": env_name,
                "client_packets": prof_obj.client_packets,
                "server_packets": prof_obj.server_packets,
                "server_total_bytes": prof_obj.server_flight_bytes + prof_obj.cert_chain_bytes,
                **summary,
            })

    # RQ3 & RQ4: Scheme & Mitigation Comparison on LEO near handover window (11.6s - 12.5s)
    mitigation_configs = [
        {"id": "unmodified", "label": "Unmodified QUIC", "scheme": "unmodified", "cert_scale": 1.0, "resumption": False, "retry": False},
        {"id": "retry_enabled", "label": "Unmodified + Retry", "scheme": "unmodified", "cert_scale": 1.0, "resumption": False, "retry": True},
        {"id": "handover_aware", "label": "Handover-Aware Scheme", "scheme": "handover_aware", "cert_scale": 1.0, "resumption": False, "retry": False},
        {"id": "cert_compressed", "label": "Cert Compression (0.65x)", "scheme": "unmodified", "cert_scale": 0.65, "resumption": False, "retry": False},
        {"id": "mtc_compact", "label": "MTC-Style Cert (0.35x)", "scheme": "handover_aware", "cert_scale": 0.35, "resumption": False, "retry": False},
        {"id": "resumption_0rtt", "label": "0-RTT Resumption", "scheme": "handover_aware", "cert_scale": 1.0, "resumption": True, "retry": False},
    ]

    rq3_rq4_mitigations = []
    for prof in ("X25519+RSA2048", "P256_Kyber768+RSA2048", "Kyber768+Dilithium3", "Kyber1024+Dilithium5"):
        for cfg in mitigation_configs:
            runs = [
                simulate_handshake(
                    starlink,
                    prof,
                    start_time_s=11.6 + (i % 10) * 0.1,
                    scheme=cfg["scheme"],
                    use_retry=cfg["retry"],
                    cert_scale=cfg["cert_scale"],
                    resumption_0rtt=cfg["resumption"],
                    seed=3000 + i,
                )
                for i in range(trials * 2)
            ]
            rq3_rq4_mitigations.append({
                "profile": prof,
                "mitigation_id": cfg["id"],
                "mitigation_label": cfg["label"],
                **summarize_runs(runs),
            })

    # Sample qlog traces for interactive packet-timeline inspection
    sample_qlogs = [
        {
            "label": "Kyber768+Dilithium3 @ t=12.0s (Unmodified QUIC)",
            "result": simulate_handshake(starlink, "Kyber768+Dilithium3", 12.0, scheme="unmodified", seed=42, record_qlog=True).__dict__,
        },
        {
            "label": "Kyber768+Dilithium3 @ t=12.0s (Handover-Aware Scheme)",
            "result": simulate_handshake(starlink, "Kyber768+Dilithium3", 12.0, scheme="handover_aware", seed=42, record_qlog=True).__dict__,
        },
        {
            "label": "X25519+RSA2048 @ t=12.0s (Classical Baseline)",
            "result": simulate_handshake(starlink, "X25519+RSA2048", 12.0, scheme="unmodified", seed=42, record_qlog=True).__dict__,
        },
    ]

    payload = {
        "metadata": {
            "project": "Handover-Aware Post-Quantum QUIC over LEO Satellite Networks",
            "handover_marks_s": [12, 27, 42, 57],
            "trials_per_cell": trials,
            "mtu_bytes": 1200,
        },
        "trace_preview": starlink[::2],  # 0.2s resolution for lightweight browser plotting
        "profiles": {k: vars(v) | {"client_packets": v.client_packets, "server_packets": v.server_packets} for k, v in PROFILES.items()},
        "rq1_handover_sweep": rq1_sweep,
        "rq2_algorithm_matrix": rq2_matrix,
        "rq3_rq4_mitigations": rq3_rq4_mitigations,
        "sample_qlogs": sample_qlogs,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PQ-QUIC LEO experiment matrix.")
    parser.add_argument("--starlink", type=Path, default=ROOT_DIR / "traces" / "starlink_15s_trace.csv")
    parser.add_argument("--terrestrial", type=Path, default=ROOT_DIR / "traces" / "terrestrial_trace.csv")
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "docs" / "data" / "benchmark_results.json")
    parser.add_argument("--trials", type=int, default=30)
    args = parser.parse_args()

    payload = run_all(args.starlink, args.terrestrial, args.output, args.trials)
    print(f"Exported benchmark results to {args.output} ({len(payload['rq2_algorithm_matrix'])} RQ2 cells, {len(payload['rq3_rq4_mitigations'])} RQ3/RQ4 cells).")


if __name__ == "__main__":
    main()

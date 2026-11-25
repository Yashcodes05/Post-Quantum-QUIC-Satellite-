"""
RFC 9000 / RFC 9002 QUIC Handshake & Anti-Amplification Transport Simulator.

Models multi-packet Initial/Handshake flights, 3x anti-amplification budget,
Retry (+1 RTT), per-packet LEO trace loss/RTT sampling, and Probe Timeout (PTO)
retransmissions, outputting metrics and qlog-compatible event traces.
"""

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from scheme.handover_aware import evaluate_initiation

MTU_PAYLOAD_BYTES = 1200


@dataclass(frozen=True)
class CryptoProfile:
    name: str
    category: str          # Classical | Hybrid | Post-Quantum | Stress
    kem: str
    signature: str
    client_hello_bytes: int
    server_flight_bytes: int
    cert_chain_bytes: int
    crypto_compute_ms: float

    @property
    def client_packets(self) -> int:
        return max(1, math.ceil(self.client_hello_bytes / MTU_PAYLOAD_BYTES))

    @property
    def server_packets(self) -> int:
        total = self.server_flight_bytes + self.cert_chain_bytes
        return max(1, math.ceil(total / MTU_PAYLOAD_BYTES))


PROFILES: Dict[str, CryptoProfile] = {
    "X25519+RSA2048": CryptoProfile(
        name="X25519+RSA2048",
        category="Classical",
        kem="X25519",
        signature="RSA-2048",
        client_hello_bytes=1200,
        server_flight_bytes=1400,
        cert_chain_bytes=2100,
        crypto_compute_ms=1.2,
    ),
    "P256_Kyber768+RSA2048": CryptoProfile(
        name="P256_Kyber768+RSA2048",
        category="Hybrid",
        kem="P-256+Kyber768",
        signature="RSA-2048",
        client_hello_bytes=2450,
        server_flight_bytes=2600,
        cert_chain_bytes=2100,
        crypto_compute_ms=1.8,
    ),
    "Kyber512+Falcon512": CryptoProfile(
        name="Kyber512+Falcon512",
        category="Post-Quantum",
        kem="Kyber512",
        signature="Falcon-512",
        client_hello_bytes=1950,
        server_flight_bytes=2200,
        cert_chain_bytes=2600,
        crypto_compute_ms=2.1,
    ),
    "Kyber768+Dilithium3": CryptoProfile(
        name="Kyber768+Dilithium3",
        category="Post-Quantum",
        kem="Kyber768",
        signature="Dilithium3",
        client_hello_bytes=3600,
        server_flight_bytes=4800,
        cert_chain_bytes=7200,
        crypto_compute_ms=2.8,
    ),
    "Kyber1024+Dilithium5": CryptoProfile(
        name="Kyber1024+Dilithium5",
        category="Post-Quantum",
        kem="Kyber1024",
        signature="Dilithium5",
        client_hello_bytes=4200,
        server_flight_bytes=6400,
        cert_chain_bytes=9200,
        crypto_compute_ms=3.6,
    ),
    "Kyber768+SPHINCS+": CryptoProfile(
        name="Kyber768+SPHINCS+",
        category="Stress",
        kem="Kyber768",
        signature="SPHINCS+-SHA256",
        client_hello_bytes=3600,
        server_flight_bytes=36000,
        cert_chain_bytes=74000,
        crypto_compute_ms=14.0,
    ),
}


@dataclass
class HandshakeResult:
    profile: str
    scheme: str
    start_time_s: float
    completion_time_ms: float
    ttfb_ms: float
    failed: bool
    rtts: int
    total_packets: int
    lost_packets: int
    pto_fires: int
    amplification_blocked: bool
    retry_used: bool
    bytes_before_validation: int
    defer_ms: float
    qlog_events: List[Dict] = field(default_factory=list)


def sample_link_at(trace: List[Dict[str, float]], t_sec: float) -> Dict[str, float]:
    """Lookup link RTT, jitter, and loss at time t_sec (wrapped to trace duration)."""
    duration = trace[-1]["time_s"] + 0.1
    t_mod = t_sec % duration
    idx = min(len(trace) - 1, max(0, int(t_mod / 0.1)))
    return trace[idx]


def simulate_handshake(
    trace: List[Dict[str, float]],
    profile_name: str,
    start_time_s: float,
    scheme: str = "unmodified",
    use_retry: bool = False,
    cert_scale: float = 1.0,
    resumption_0rtt: bool = False,
    max_handshake_timeout_ms: float = 4000.0,
    seed: Optional[int] = None,
    record_qlog: bool = False,
) -> HandshakeResult:
    """
    Simulate one QUIC handshake over a time-varying link trace.
    """
    rng = random.Random(seed)
    base_profile = PROFILES[profile_name]
    qlog: List[Dict] = []

    def log_ev(t_ms: float, name: str, data: Dict) -> None:
        if record_qlog:
            qlog.append({"time_ms": round(t_ms, 2), "name": name, "data": data})

    link0 = sample_link_at(trace, start_time_s)
    defer_ms = 0.0
    active_profile = base_profile
    pto_base_ms = max(250.0, link0["rtt_ms"] * 3.0)

    if scheme == "handover_aware":
        est_ms = link0["rtt_ms"] * 2.0 + base_profile.crypto_compute_ms
        decision = evaluate_initiation(
            start_time_s=start_time_s,
            estimated_handshake_ms=est_ms,
            base_rtt_ms=link0["rtt_ms"],
            requested_profile=profile_name,
        )
        defer_ms = decision.defer_ms
        pto_base_ms = decision.recommended_pto_ms
        active_profile = PROFILES[decision.selected_profile]
        if defer_ms > 0:
            log_ev(0.0, "scheme:defer_initiation", {"defer_ms": defer_ms, "reason": decision.reason})

    cur_t_s = start_time_s + (defer_ms / 1000.0)
    elapsed_ms = 0.0
    rtts = 0
    total_packets = 0
    lost_packets = 0
    pto_fires = 0

    if resumption_0rtt:
        # 0-RTT sends application data alongside 1-packet Initial; minimal server flight
        client_pkts = 2
        server_pkts = 2
        server_bytes = 1800
    else:
        client_pkts = active_profile.client_packets
        scaled_cert = int(active_profile.cert_chain_bytes * cert_scale)
        server_bytes = active_profile.server_flight_bytes + scaled_cert
        server_pkts = max(1, math.ceil(server_bytes / MTU_PAYLOAD_BYTES))

    client_initial_bytes = max(1200, client_pkts * MTU_PAYLOAD_BYTES)
    amplification_limit = 3 * client_initial_bytes
    amplification_blocked = server_bytes > amplification_limit

    # Optional Retry (+1 RTT) or anti-amplification extra RTT stall
    if use_retry:
        rtts += 1
        link = sample_link_at(trace, cur_t_s)
        step_ms = max(5.0, link["rtt_ms"] + rng.gauss(0, link["jitter_ms"] * 0.3))
        total_packets += 2
        if rng.random() < (link["loss_pct"] / 100.0):
            lost_packets += 1
            pto_fires += 1
            step_ms += pto_base_ms
        elapsed_ms += step_ms
        cur_t_s += step_ms / 1000.0
        log_ev(elapsed_ms, "transport:retry_completed", {"rtt_ms": round(step_ms, 2)})

    # Flight 1: Client Initial -> Server Initial + Handshake
    # If amplification_blocked and not use_retry, server pauses at 3x until client ACKs (+1 RTT)
    extra_amp_rtt = 1 if (amplification_blocked and not use_retry) else 0
    flights_needed = 1 + extra_amp_rtt + (0 if resumption_0rtt else 1)

    for flight_idx in range(flights_needed):
        if elapsed_ms >= max_handshake_timeout_ms:
            break
        rtts += 1
        link = sample_link_at(trace, cur_t_s)
        loss_prob = min(0.95, max(0.0, link["loss_pct"] / 100.0))

        pkts_this_flight = client_pkts if flight_idx == 0 else max(1, math.ceil(server_pkts / max(1, flights_needed - 1)))
        total_packets += pkts_this_flight

        # Check packet losses in this flight
        losses_in_flight = sum(1 for _ in range(pkts_this_flight) if rng.random() < loss_prob)
        lost_packets += losses_in_flight

        flight_rtt = max(5.0, link["rtt_ms"] + rng.gauss(0, link["jitter_ms"] * 0.35))
        if flight_idx == 0:
            flight_rtt += active_profile.crypto_compute_ms

        elapsed_ms += flight_rtt
        cur_t_s += flight_rtt / 1000.0
        log_ev(elapsed_ms, "transport:flight_sent", {
            "flight": flight_idx + 1,
            "packets": pkts_this_flight,
            "lost": losses_in_flight,
            "rtt_ms": round(flight_rtt, 2),
        })

        # Retransmission loop via RFC 9002 PTO if any packet in flight was lost
        pto_backoff = 1.0
        remaining_losses = losses_in_flight
        while remaining_losses > 0 and elapsed_ms < max_handshake_timeout_ms:
            pto_fires += 1
            wait_pto = pto_base_ms * pto_backoff
            elapsed_ms += wait_pto
            cur_t_s += wait_pto / 1000.0

            link_retx = sample_link_at(trace, cur_t_s)
            retx_loss_prob = min(0.95, max(0.0, link_retx["loss_pct"] / 100.0))
            total_packets += remaining_losses
            new_losses = sum(1 for _ in range(remaining_losses) if rng.random() < retx_loss_prob)
            lost_packets += new_losses

            retx_rtt = max(5.0, link_retx["rtt_ms"] + rng.gauss(0, link_retx["jitter_ms"] * 0.3))
            elapsed_ms += retx_rtt
            cur_t_s += retx_rtt / 1000.0
            log_ev(elapsed_ms, "recovery:pto_retransmit", {
                "pto_ms": round(wait_pto, 2),
                "retransmitted": remaining_losses,
                "lost_again": new_losses,
            })
            remaining_losses = new_losses
            if scheme == "handover_aware":
                pto_backoff = min(2.0, pto_backoff * 1.25)
            else:
                pto_backoff = min(8.0, pto_backoff * 2.0)

    failed = elapsed_ms >= max_handshake_timeout_ms
    total_time_ms = elapsed_ms + defer_ms
    ttfb_ms = total_time_ms if resumption_0rtt else total_time_ms + sample_link_at(trace, cur_t_s)["rtt_ms"] * 0.5

    return HandshakeResult(
        profile=active_profile.name,
        scheme=scheme,
        start_time_s=round(start_time_s, 3),
        completion_time_ms=round(min(total_time_ms, max_handshake_timeout_ms), 2),
        ttfb_ms=round(min(ttfb_ms, max_handshake_timeout_ms + 100.0), 2),
        failed=failed,
        rtts=rtts,
        total_packets=total_packets,
        lost_packets=lost_packets,
        pto_fires=pto_fires,
        amplification_blocked=amplification_blocked,
        retry_used=use_retry,
        bytes_before_validation=min(server_bytes, amplification_limit),
        defer_ms=round(defer_ms, 2),
        qlog_events=qlog,
    )

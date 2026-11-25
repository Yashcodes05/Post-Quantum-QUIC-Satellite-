"""
Handover-Aware Post-Quantum QUIC Connection Establishment Scheme.

Implements three cross-layer / transport-level optimizations for LEO links:
1. Schedule-Aware Initiation: Predicts Starlink's 15-second handover marks
   (12s, 27s, 42s, 57s of each minute) and defers handshakes that would collide
   with an imminent blackout window.
2. Adaptive PTO (RFC 9002): Clamps/aligns Probe Timeout backoff around predicted
   handover recovery so a brief burst does not cause multi-second stalls.
3. Dynamic Profile Selection: Selects compact PQ/hybrid profiles (or 0-RTT/MTC)
   when operating near a handover boundary or elevated loss regime.
"""

from dataclasses import dataclass
from typing import Tuple

STARLINK_HANDOVER_MARKS = (12.0, 27.0, 42.0, 57.0)
HANDOVER_GUARD_PRE_S = 0.35   # Guard window before handover mark
HANDOVER_DURATION_S = 0.45    # Typical handover disruption + recovery window


@dataclass
class HandoverDecision:
    """Result of the handover-aware connection establishment controller."""
    defer_ms: float
    recommended_pto_ms: float
    selected_profile: str
    reason: str


def time_to_next_handover(t_sec: float) -> Tuple[float, float]:
    """Return (seconds_until_next_mark, next_mark_in_minute) for a 60s cycle."""
    t_mod = t_sec % 60.0
    for mark in STARLINK_HANDOVER_MARKS:
        if t_mod <= mark + HANDOVER_DURATION_S:
            return mark - t_mod, mark
    # Next mark is 12.0s of the next minute
    return (60.0 - t_mod) + STARLINK_HANDOVER_MARKS[0], STARLINK_HANDOVER_MARKS[0]


def evaluate_initiation(
    start_time_s: float,
    estimated_handshake_ms: float,
    base_rtt_ms: float,
    requested_profile: str,
    enable_defer: bool = True,
    enable_adaptive_pto: bool = True,
    enable_profile_adapt: bool = True,
) -> HandoverDecision:
    """
    Decide initiation timing, PTO tuning, and handshake profile relative to
    the 15-second Starlink handover schedule.
    """
    delta_s, next_mark = time_to_next_handover(start_time_s)
    est_s = estimated_handshake_ms / 1000.0

    defer_ms = 0.0
    reason = "clear_window"
    selected_profile = requested_profile

    # Case 1: Currently inside a handover disruption window (-0.15s .. +0.45s)
    if -HANDOVER_DURATION_S <= delta_s <= 0.15:
        if enable_defer:
            wait_s = max(0.05, (HANDOVER_DURATION_S + delta_s) + 0.05)
            defer_ms = wait_s * 1000.0
            reason = f"inside_handover_{int(next_mark)}s_defer"
    # Case 2: Handshake flight will collide with an upcoming handover mark
    elif 0.15 < delta_s < (est_s + HANDOVER_GUARD_PRE_S):
        if enable_defer:
            defer_ms = (delta_s + HANDOVER_DURATION_S + 0.05) * 1000.0
            reason = f"pre_handover_collision_{int(next_mark)}s_defer"
        elif enable_profile_adapt and requested_profile in ("Kyber768+Dilithium3", "Kyber1024+Dilithium5", "Kyber768+SPHINCS+"):
            selected_profile = "Kyber512+Falcon512"
            reason = "near_handover_compact_profile"

    # Adaptive PTO: avoid 1000ms+ exponential backoff spikes; align with RTT + jitter
    if enable_adaptive_pto:
        recommended_pto_ms = max(120.0, min(260.0, base_rtt_ms * 2.2))
    else:
        recommended_pto_ms = max(300.0, base_rtt_ms * 3.0)

    return HandoverDecision(
        defer_ms=round(defer_ms, 2),
        recommended_pto_ms=round(recommended_pto_ms, 2),
        selected_profile=selected_profile,
        reason=reason,
    )

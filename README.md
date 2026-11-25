# Handover-Aware Post-Quantum QUIC Connection Establishment over LEO Satellite Networks

[![Deploy Interactive Analyzer to GitHub Pages](https://github.com/Yashcodes05/Post-Quantum-QUIC-Satellite-/actions/workflows/pages.yml/badge.svg)](https://github.com/Yashcodes05/Post-Quantum-QUIC-Satellite-/actions/workflows/pages.yml)

**Live Interactive Analyzer (GitHub Pages):**  
👉 **https://yashcodes05.github.io/Post-Quantum-QUIC-Satellite-/**

An **Advanced Computer Networks (ACN)** research & engineering project studying how **Post-Quantum Cryptography (PQC)** handshakes in **QUIC** interact with **15-second periodic LEO satellite (Starlink) link handovers**, and evaluating a **Handover-Aware Connection Establishment Scheme** plus certificate-size & resumption mitigations.

---

## Why This is an ACN (Transport & Network Layer) Project

While prior PQC-QUIC benchmarks run on `< 0.1 ms` loss-free terrestrial testbeds and prior LEO transport work (StarQUIC, SatPipe, SaTCP, LeoCC) focuses on congestion control *after* connection setup, this project targets the **connection-establishment phase**:

1. **Multi-Packet Handshake Exposure $(1 - p)^N$:** PQ key exchanges (ML-KEM/Kyber) and signatures (ML-DSA/Dilithium, Falcon, SPHINCS+) expand server handshake flights from ~3 packets (RSA-2048) to 10–92 packets.
2. **QUIC Anti-Amplification Limit (`3×` Rule) & Address Validation:** Larger PQ certificate chains trigger QUIC's `3×` unvalidated-byte cap and `Retry` packets (`+1 RTT`).
3. **15-Second LEO Handover Collisions (`12, 27, 42, 57s` marks):** Handover-induced RTT spikes and burst packet loss trigger RFC 9002 Probe Timeouts (PTO) and exponential backoff during the handshake.
4. **Handover-Aware Establishment Scheme:** Schedule-aware handshake initiation, adaptive PTO/retransmission pacing around handover windows, and dynamic profile/resumption selection.

---

## Repository Architecture

```text
├── docs/                       # Interactive GitHub Pages Frontend (zero-build HTML/CSS/JS)
│   ├── index.html              # Dashboard: RQ1–RQ4 views, Handover Timeline, qlog/JSON uploader
│   ├── styles.css              # Dark network-telemetry UI theme
│   ├── app.js                  # Interactive charts, RFC 9002/9000 transport simulator & analyzer
│   └── data/                   # Pre-generated trace & benchmark JSON datasets
├── docker/
│   ├── Dockerfile              # Ubuntu 24.04 + iproute2 (tc/netem) + Python + OQS/QUIC tooling
│   └── docker-compose.yml      # Isolated Client <-> NetEm Router <-> Server topology
├── traces/
│   ├── starlink_15s_trace.csv  # 60s LEO trace with 12/27/42/57s handover RTT & loss bursts
│   └── terrestrial_trace.csv   # Stable terrestrial baseline trace
├── emulator/
│   └── replay_trace.py         # Drives Linux `tc netem` dynamically from CSV traces
├── scheme/
│   └── handover_aware.py       # Handover-Aware QUIC initiation, adaptive PTO & profile selector
├── experiments/
│   ├── quic_transport_sim.py   # RFC 9000/9002 QUIC handshake + 3x anti-amplification simulator
│   └── run_matrix.py           # Sweeps RQ1–RQ4 matrix & exports JSON/CSV for docs/ and analysis/
├── analysis/
│   └── analyze_qlog.py         # Parses qlog / experiment JSON & prints summary tables
└── .github/workflows/pages.yml # Auto-deploys docs/ to GitHub Pages on push to main
```

---

## Quick Start

### 1. View & Use the Interactive Analyzer Locally
Open `docs/index.html` via a local HTTP server:
```bash
python -m http.server 8080 --directory docs
# Visit http://localhost:8080
```
Or visit the deployed GitHub Pages site directly once Pages is enabled in **Repository Settings → Pages → Source: GitHub Actions**.

### 2. Run the Experiment & Trace Matrix (Python 3.10+)
Re-generate the full RQ1–RQ4 dataset (`docs/data/benchmark_results.json`) and view CLI telemetry tables:
```bash
python experiments/run_matrix.py
python analysis/analyze_qlog.py docs/data/benchmark_results.json
```
You can also upload any generated `.json` or `qlog` file directly into the **Upload & Inspect Trace/qlog** tab on the GitHub Pages frontend.

### 3. Run Real Linux `tc/netem` Emulation via Docker
Requires Docker with Linux containers (`NET_ADMIN` capability for `tc/netem`):
```bash
cd docker
docker compose up --build
```
Inside the router container, `emulator/replay_trace.py` applies real-time `tc qdisc change dev eth0 root netem delay ... loss ...` updates every 100 ms from `traces/starlink_15s_trace.csv`.

---

## Research Questions Covered

| RQ | Focus | Interactive View in Frontend |
|----|-------|------------------------------|
| **RQ1** | Handover start-time offset across the 15s cycle (`12, 27, 42, 57s`) | **Handover Cycle Sweep** chart & live timeline |
| **RQ2** | PQ algorithm size, packet count $N$, and `3×` anti-amplification limit | **Algorithm & Amplification Matrix** |
| **RQ3** | Handover-Aware Scheme vs. Unmodified QUIC (latency & failure rate) | **Scheme Comparison & Simulator** |
| **RQ4** | Certificate compression, MTC-style size reduction, and 0-RTT resumption | **Mitigation Impact Analyzer** |

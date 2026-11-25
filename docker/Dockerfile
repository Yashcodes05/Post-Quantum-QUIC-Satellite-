FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    iproute2 \
    iputils-ping \
    tcpdump \
    tshark \
    python3 \
    python3-pip \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY traces/ /workspace/traces/
COPY emulator/ /workspace/emulator/
COPY scheme/ /workspace/scheme/
COPY experiments/ /workspace/experiments/
COPY analysis/ /workspace/analysis/

CMD ["python3", "/workspace/emulator/replay_trace.py", "--trace", "/workspace/traces/starlink_15s_trace.csv", "--dry-run"]

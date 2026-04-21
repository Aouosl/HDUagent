FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN sed -i 's|http://archive.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list && \
    sed -i 's|http://security.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    tshark tcpdump nmap \
    netcat-openbsd curl wget dnsutils whois \
    binwalk foremost file xxd \
    python3 python3-pip python3-venv \
    jq tree less unzip git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir sqlmap

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /workspace /app/memory /app/runs /app/playbooks /app/knowledge

ENV WORKSPACE=/workspace
ENV CTF_WORKSPACE_ROOT=/workspace
ENV MEMORY_DIR=/app/memory
ENV RUNS_DIR=/app/runs
ENV PLAYBOOKS_DIR=/app/playbooks
ENV ENABLE_MCP=false
ENV AGENT_MAX_ROUNDS=60

ENTRYPOINT ["python3", "main.py"]

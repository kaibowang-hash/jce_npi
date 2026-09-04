FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm@sha256:b726eb94f42fcddb10056835f2c474c9f9e12e717ba2b2d2f9a8b1d78feeb68b

ARG BENCH_VERSION=5.31.0

RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
        sed -i '/dl\.yarnpkg\.com\/debian/d' /etc/apt/sources.list; \
    fi; \
    find /etc/apt/sources.list.d -maxdepth 1 -type f -iname '*yarn*' -delete; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        make \
        mariadb-client \
        redis-tools; \
    python -m venv /opt/frappe-bench; \
    /opt/frappe-bench/bin/pip install --no-cache-dir "frappe-bench==${BENCH_VERSION}"; \
    chmod -R a+rX /opt/frappe-bench; \
    ln -s /opt/frappe-bench/bin/bench /usr/local/bin/bench; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

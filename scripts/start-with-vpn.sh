#!/bin/bash
# Start wireproxy (WireGuard → SOCKS5 proxy) then launch gunicorn.
# wireproxy runs in userspace — no root/kernel modules needed.

set -e

WIREPROXY_PORT=25344
WIREPROXY_BIN="/opt/render/project/src/wireproxy"
WIREPROXY_CONF="/tmp/wireproxy.conf"

# --- 1. If WIREGUARD_CONFIG env is set, decode it and start wireproxy ---
if [ -n "$WIREGUARD_CONFIG" ]; then
    echo "[polybacker] WireGuard config detected — starting wireproxy..."

    # Decode base64 WireGuard config
    echo "$WIREGUARD_CONFIG" | base64 -d > /tmp/wg-base.conf

    # Build wireproxy config: WireGuard config + SOCKS5 listener
    cat /tmp/wg-base.conf > "$WIREPROXY_CONF"
    echo "" >> "$WIREPROXY_CONF"
    echo "[Socks5]" >> "$WIREPROXY_CONF"
    echo "BindAddress = 127.0.0.1:${WIREPROXY_PORT}" >> "$WIREPROXY_CONF"

    echo "[polybacker] wireproxy config:"
    grep -v "PrivateKey" "$WIREPROXY_CONF" | head -20

    # Download wireproxy if not cached
    if [ ! -f "$WIREPROXY_BIN" ]; then
        echo "[polybacker] Downloading wireproxy..."
        WIREPROXY_VERSION="1.0.9"
        curl -sL "https://github.com/whyvl/wireproxy/releases/download/v${WIREPROXY_VERSION}/wireproxy_linux_amd64.tar.gz" \
            | tar xz -C /opt/render/project/src/ wireproxy
        chmod +x "$WIREPROXY_BIN"
        echo "[polybacker] wireproxy downloaded: $($WIREPROXY_BIN --version 2>&1 || echo 'ok')"
    fi

    # Start wireproxy in background
    "$WIREPROXY_BIN" -c "$WIREPROXY_CONF" -d &
    WIREPROXY_PID=$!
    echo "[polybacker] wireproxy started (PID=$WIREPROXY_PID)"

    # Wait for SOCKS5 proxy to be ready
    for i in $(seq 1 15); do
        if curl -s --max-time 2 --socks5 "127.0.0.1:${WIREPROXY_PORT}" https://httpbin.org/ip > /dev/null 2>&1; then
            echo "[polybacker] SOCKS5 proxy ready on port $WIREPROXY_PORT"
            # Show our exit IP to confirm we're not US
            EXIT_IP=$(curl -s --max-time 5 --socks5 "127.0.0.1:${WIREPROXY_PORT}" https://httpbin.org/ip 2>/dev/null || echo "unknown")
            echo "[polybacker] Exit IP: $EXIT_IP"
            break
        fi
        echo "[polybacker] Waiting for wireproxy... ($i/15)"
        sleep 2
    done

    # Set proxy URL for the Python app
    export PROXY_URL="socks5://127.0.0.1:${WIREPROXY_PORT}"
    echo "[polybacker] PROXY_URL=$PROXY_URL"
fi

# --- 2. Start gunicorn ---
echo "[polybacker] Starting gunicorn..."
exec gunicorn --worker-class gthread -w 1 --threads 4 --bind "0.0.0.0:$PORT" \
    'polybacker.server:create_wsgi_app()'

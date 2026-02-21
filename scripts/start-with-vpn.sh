#!/bin/bash
# Start wireproxy (WireGuard → SOCKS5 proxy) then launch gunicorn.
# wireproxy runs in userspace — no root/kernel modules needed.
# NOTE: We intentionally do NOT use set -e so wireproxy failures
# don't prevent gunicorn from starting.

WIREPROXY_PORT=25344
WIREPROXY_BIN="/opt/render/project/src/wireproxy"
WIREPROXY_CONF="/tmp/wireproxy.conf"

# --- 1. If WIREGUARD_CONFIG env is set, decode it and start wireproxy ---
if [ -n "$WIREGUARD_CONFIG" ]; then
    echo "[polybacker] WireGuard config detected — starting wireproxy..."

    # Decode base64 WireGuard config
    echo "$WIREGUARD_CONFIG" | base64 -d > /tmp/wg-base.conf 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "[polybacker] ERROR: Failed to decode WIREGUARD_CONFIG (bad base64?)"
        echo "[polybacker] Continuing without VPN proxy..."
    else
        # Strip ProtonVPN comment lines that wireproxy doesn't understand
        grep -v '^#' /tmp/wg-base.conf > /tmp/wg-clean.conf

        # Build wireproxy config: cleaned WireGuard config + SOCKS5 listener
        cat /tmp/wg-clean.conf > "$WIREPROXY_CONF"
        printf '\n[Socks5]\nBindAddress = 127.0.0.1:%s\n' "$WIREPROXY_PORT" >> "$WIREPROXY_CONF"

        echo "[polybacker] wireproxy config (redacted):"
        grep -v "PrivateKey" "$WIREPROXY_CONF" || true

        # Download wireproxy if not cached
        if [ ! -f "$WIREPROXY_BIN" ]; then
            echo "[polybacker] Downloading wireproxy..."
            WIREPROXY_VERSION="1.0.9"
            curl -sL "https://github.com/whyvl/wireproxy/releases/download/v${WIREPROXY_VERSION}/wireproxy_linux_amd64.tar.gz" \
                -o /tmp/wireproxy.tar.gz

            if [ $? -ne 0 ] || [ ! -s /tmp/wireproxy.tar.gz ]; then
                echo "[polybacker] ERROR: Failed to download wireproxy"
                echo "[polybacker] Continuing without VPN proxy..."
            else
                tar xz -C /opt/render/project/src/ -f /tmp/wireproxy.tar.gz wireproxy 2>/dev/null
                if [ $? -ne 0 ]; then
                    echo "[polybacker] ERROR: Failed to extract wireproxy"
                    echo "[polybacker] Continuing without VPN proxy..."
                else
                    chmod +x "$WIREPROXY_BIN"
                    echo "[polybacker] wireproxy downloaded OK"
                fi
            fi
        else
            echo "[polybacker] wireproxy binary already cached"
        fi

        # Start wireproxy in background if binary exists
        if [ -f "$WIREPROXY_BIN" ]; then
            "$WIREPROXY_BIN" -c "$WIREPROXY_CONF" &
            WIREPROXY_PID=$!
            echo "[polybacker] wireproxy started (PID=$WIREPROXY_PID)"

            # Wait for SOCKS5 proxy to be ready
            PROXY_READY=0
            for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
                if curl -s --max-time 3 --socks5-hostname "127.0.0.1:${WIREPROXY_PORT}" https://httpbin.org/ip > /dev/null 2>&1; then
                    echo "[polybacker] SOCKS5 proxy ready on port $WIREPROXY_PORT"
                    EXIT_IP=$(curl -s --max-time 5 --socks5-hostname "127.0.0.1:${WIREPROXY_PORT}" https://httpbin.org/ip 2>/dev/null || echo "unknown")
                    echo "[polybacker] Exit IP: $EXIT_IP"
                    PROXY_READY=1
                    break
                fi
                echo "[polybacker] Waiting for wireproxy... ($i/15)"
                sleep 2
            done

            if [ "$PROXY_READY" -eq 0 ]; then
                echo "[polybacker] WARNING: wireproxy did not become ready after 30s"
                if ! kill -0 "$WIREPROXY_PID" 2>/dev/null; then
                    echo "[polybacker] wireproxy process died — check config"
                fi
                echo "[polybacker] Continuing — gunicorn will start but trades may fail"
            fi

            export PROXY_URL="socks5://127.0.0.1:${WIREPROXY_PORT}"
            echo "[polybacker] PROXY_URL=$PROXY_URL"
        fi
    fi
else
    echo "[polybacker] No WIREGUARD_CONFIG set — starting without VPN proxy"
fi

# --- 2. Start gunicorn (this MUST succeed) ---
echo "[polybacker] Starting gunicorn..."
exec gunicorn --worker-class gthread -w 1 --threads 4 --bind "0.0.0.0:$PORT" \
    'polybacker.server:create_wsgi_app()'

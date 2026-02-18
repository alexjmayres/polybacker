"use client";

import { useEffect, useState } from "react";
import { io, type Socket } from "socket.io-client";
import { API_BASE } from "@/lib/config";

interface BotStatus {
  copy_trading: "running" | "stopped";
  arbitrage: "running" | "stopped";
}

export function useSocket() {
  const [status, setStatus] = useState<BotStatus>({
    copy_trading: "stopped",
    arbitrage: "stopped",
  });
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let socket: Socket | null = null;
    let retryTimer: ReturnType<typeof setInterval> | null = null;
    let retries = 0;

    const connect = () => {
      const token = localStorage.getItem("polybacker_token");
      if (!token) {
        if (retries < 20) {
          retries++;
          return; // interval will retry
        }
        // Give up after 10s (20 * 500ms)
        if (retryTimer) {
          clearInterval(retryTimer);
          retryTimer = null;
        }
        return;
      }

      // Token found — stop retrying and connect
      if (retryTimer) {
        clearInterval(retryTimer);
        retryTimer = null;
      }

      socket = io(API_BASE || undefined, {
        auth: { token },
        transports: ["websocket", "polling"],
      });

      socket.on("connect", () => setConnected(true));
      socket.on("disconnect", () => setConnected(false));
      socket.on("status", (data: BotStatus) => setStatus(data));
    };

    // Try immediately, then retry every 500ms if no token yet
    connect();
    if (!socket) {
      retryTimer = setInterval(connect, 500);
    }

    return () => {
      if (retryTimer) clearInterval(retryTimer);
      if (socket) socket.disconnect();
    };
  }, []);

  return { status, connected };
}

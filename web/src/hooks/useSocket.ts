"use client";

import { useEffect, useState } from "react";
import { io, type Socket } from "socket.io-client";

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
    const token = localStorage.getItem("polybacker_token");
    if (!token) return;

    const socket: Socket = io({
      auth: { token },
      transports: ["websocket", "polling"],
    });

    socket.on("connect", () => setConnected(true));
    socket.on("disconnect", () => setConnected(false));
    socket.on("status", (data: BotStatus) => setStatus(data));

    return () => {
      socket.disconnect();
    };
  }, []);

  return { status, connected };
}

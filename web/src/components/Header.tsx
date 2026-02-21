"use client";

import { useState, useCallback } from "react";
import { ConnectButton } from "@rainbow-me/rainbowkit";
import { useQueryClient } from "@tanstack/react-query";
import { StatusBadge } from "./StatusBadge";

interface HeaderProps {
  onLogoClick?: () => void;
  copyStatus?: "running" | "stopped";
  arbStatus?: "running" | "stopped";
  connected?: boolean;
}

export function Header({ onLogoClick, copyStatus, arbStatus, connected }: HeaderProps) {
  const queryClient = useQueryClient();
  const [spinning, setSpinning] = useState(false);

  const handleRefresh = useCallback(() => {
    setSpinning(true);
    queryClient.invalidateQueries();
    setTimeout(() => setSpinning(false), 800);
  }, [queryClient]);

  return (
    <header className="glass border-b border-[var(--panel-border)] sticky top-0 z-50 rounded-none">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3">
        <div className="flex items-center justify-between">
          <button
            onClick={onLogoClick}
            className="flex items-center gap-3 sm:gap-4 hover:opacity-80 transition-opacity"
            title="Back to home"
          >
            <div className="w-8 h-8 sm:w-10 sm:h-10 border border-[var(--green)] flex items-center justify-center pulse-glow">
              <span className="pixel text-[var(--green)] text-[10px] sm:text-xs">PB</span>
            </div>
            <div className="text-left">
              <h1
                className="pixel text-xs sm:text-sm text-[var(--green)]"
                style={{ textShadow: "0 0 15px rgba(0,255,65,0.5)" }}
              >
                POLYBACKER
              </h1>
              <p className="mono text-[10px] sm:text-xs text-[var(--green-dim)] opacity-60 hidden sm:block">
                copy trading & arbitrage terminal
              </p>
            </div>
          </button>
          <div className="flex items-center gap-2 sm:gap-3">
            <button
              onClick={handleRefresh}
              title="Refresh all data"
              className="w-8 h-8 flex items-center justify-center border border-[rgba(0,255,65,0.15)] hover:border-[var(--green)] hover:bg-[rgba(0,255,65,0.08)] text-[var(--green-dark)] hover:text-[var(--green)] transition-all"
            >
              <span
                className="mono text-sm"
                style={{
                  display: "inline-block",
                  transition: "transform 0.8s ease",
                  transform: spinning ? "rotate(360deg)" : "rotate(0deg)",
                }}
              >
                ↻
              </span>
            </button>
            <div className="hidden sm:flex items-center gap-2">
              <StatusBadge
                status={connected ? (copyStatus ?? "stopped") : "loading"}
                label="COPY"
              />
              <StatusBadge
                status={connected ? (arbStatus ?? "stopped") : "loading"}
                label="ARB"
              />
            </div>
            <ConnectButton />
          </div>
        </div>
      </div>
    </header>
  );
}

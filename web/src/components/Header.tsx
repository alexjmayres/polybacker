"use client";

import { ConnectButton } from "@rainbow-me/rainbowkit";

export function Header() {
  return (
    <header className="glass border-b border-[var(--panel-border)] sticky top-0 z-50 rounded-none">
      <div className="max-w-7xl mx-auto px-6 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 border border-[var(--green)] flex items-center justify-center pulse-glow">
              <span className="pixel text-[var(--green)] text-xs">PB</span>
            </div>
            <div>
              <h1 className="pixel text-sm text-[var(--green)]" style={{ textShadow: "0 0 15px rgba(0,255,65,0.5)" }}>
                POLYBACKER
              </h1>
              <p className="mono text-xs text-[var(--green-dim)] opacity-60">
                copy trading & arbitrage terminal
              </p>
            </div>
          </div>
          <ConnectButton />
        </div>
      </div>
    </header>
  );
}

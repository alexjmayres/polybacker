"use client";

import { useState, useEffect } from "react";
import { ConnectButton } from "@rainbow-me/rainbowkit";
import { useAccount } from "wagmi";
import { Header } from "@/components/Header";
import { TabNav } from "@/components/TabNav";
import { CopyPanel } from "@/components/copy/CopyPanel";
import { ArbPanel } from "@/components/arb/ArbPanel";
import { useAuth } from "@/hooks/useAuth";

function TerminalLine({ children, delay = 0 }: { children: string; delay?: number }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(t);
  }, [delay]);

  if (!visible) return null;
  return (
    <div className="mono text-sm slide-up">
      <span className="text-[var(--green-dim)] opacity-50">$</span>{" "}
      <span className="text-[var(--green)]">{children}</span>
    </div>
  );
}

function Landing() {
  return (
    <div className="min-h-screen flex flex-col">
      <div className="relative z-10 flex flex-col items-center justify-center flex-1 px-6 py-16">
        {/* ASCII logo */}
        <div className="mb-8 text-center">
          <pre
            className="pixel text-[var(--green)] text-[8px] sm:text-[10px] md:text-xs leading-tight"
            style={{ textShadow: "0 0 20px rgba(0,255,65,0.6)" }}
          >
{`
 ######   ######  ##   ##  ## ######   ######  ######  ##  ## ###### ######
 ##  ##  ##    ## ##    ## ##  ##  ##  ##    ## ##      ## ##  ##     ##  ##
 ##  ##  ##    ## ##     ###   ##  ##  ##    ## ##      ####   ##     ##  ##
 ######  ##    ## ##     ##    ######  ######## ##      ###    #####  ######
 ##      ##    ## ##     ##    ##  ##  ##    ## ##      ####   ##     ## ##
 ##      ##    ## ##     ##    ##  ##  ##    ## ##      ## ##  ##     ##  ##
 ##       ######  ###### ##    ######  ##    ## ######  ##  ## ###### ##  ##
`}
          </pre>
        </div>

        {/* Terminal window */}
        <div className="max-w-lg w-full glass rounded-none p-0 mb-8 overflow-hidden">
          {/* Title bar */}
          <div className="flex items-center gap-2 px-4 py-2 border-b border-[var(--panel-border)] bg-[rgba(0,255,65,0.05)]">
            <span className="text-[var(--red)] text-[8px]">&#9679;</span>
            <span className="text-[var(--amber)] text-[8px]">&#9679;</span>
            <span className="text-[var(--green)] text-[8px]">&#9679;</span>
            <span className="mono text-xs text-[var(--green-dim)] ml-2">polybacker@polygon:~</span>
          </div>
          {/* Terminal body */}
          <div className="p-4 space-y-1">
            <TerminalLine delay={200}>polybacker v0.1.0 -- trading terminal</TerminalLine>
            <TerminalLine delay={600}>init copy_trading_engine... OK</TerminalLine>
            <TerminalLine delay={1000}>init arbitrage_scanner... OK</TerminalLine>
            <TerminalLine delay={1400}>connecting to polygon mainnet... OK</TerminalLine>
            <TerminalLine delay={1800}>all systems nominal</TerminalLine>
            <div className="mt-3 pt-3 border-t border-[var(--panel-border)]">
              <TerminalLine delay={2200}>awaiting wallet authentication_</TerminalLine>
            </div>
          </div>
        </div>

        {/* Connect button */}
        <div className="mb-12">
          <ConnectButton label="[ CONNECT WALLET ]" />
        </div>

        {/* Feature cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-3xl w-full">
          <div className="glass rounded-none p-5 slide-up">
            <div className="text-[var(--cyan)] pixel text-[10px] mb-3">[01]</div>
            <h3 className="text-[var(--green)] font-bold mb-2 uppercase text-sm tracking-wider">
              Copy Trading
            </h3>
            <p className="text-xs text-[var(--green-dim)] opacity-70 leading-relaxed">
              Follow top traders and automatically mirror their positions
            </p>
          </div>
          <div className="glass rounded-none p-5 slide-up" style={{ animationDelay: "0.1s" }}>
            <div className="text-[var(--amber)] pixel text-[10px] mb-3">[02]</div>
            <h3 className="text-[var(--green)] font-bold mb-2 uppercase text-sm tracking-wider">
              Arbitrage
            </h3>
            <p className="text-xs text-[var(--green-dim)] opacity-70 leading-relaxed">
              Scan for pricing inefficiencies and capture risk-free profit
            </p>
          </div>
          <div className="glass rounded-none p-5 slide-up" style={{ animationDelay: "0.2s" }}>
            <div className="text-[var(--magenta)] pixel text-[10px] mb-3">[03]</div>
            <h3 className="text-[var(--green)] font-bold mb-2 uppercase text-sm tracking-wider">
              Non-Custodial
            </h3>
            <p className="text-xs text-[var(--green-dim)] opacity-70 leading-relaxed">
              Sign in with your wallet. Your keys, your control.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-12 mono text-xs text-[var(--green-dark)]">
          polybacker.com // built on polygon // powered by polymarket
        </div>
      </div>
    </div>
  );
}

function Dashboard() {
  const [activeTab, setActiveTab] = useState<"copy" | "arb">("copy");

  return (
    <div className="min-h-screen">
      <div className="relative z-10">
        <Header />
        <main className="max-w-7xl mx-auto px-6 py-8">
          <TabNav activeTab={activeTab} onTabChange={setActiveTab} />
          {activeTab === "copy" ? <CopyPanel /> : <ArbPanel />}
        </main>
      </div>
    </div>
  );
}

export default function Home() {
  const { isAuthenticated, isLoading } = useAuth();
  const { isConnected } = useAccount();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="mono text-lg text-[var(--green)]">
          LOADING<span className="blink">_</span>
        </div>
      </div>
    );
  }

  if (!isConnected || !isAuthenticated) {
    return <Landing />;
  }

  return <Dashboard />;
}

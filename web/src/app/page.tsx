"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { ConnectButton } from "@rainbow-me/rainbowkit";
import { useAccount } from "wagmi";
import { Header } from "@/components/Header";
import { TabNav } from "@/components/TabNav";
import type { Tab } from "@/components/TabNav";
import { SummaryPanel } from "@/components/summary/SummaryPanel";
import { CopyPanel } from "@/components/copy/CopyPanel";
import { ArbPanel } from "@/components/arb/ArbPanel";
import { PositionsPanel } from "@/components/positions/PositionsPanel";
import { FundPanel } from "@/components/fund/FundPanel";
import { WatchlistPanel } from "@/components/watchlist/WatchlistPanel";
import { AdminPanel } from "@/components/admin/AdminPanel";
import { SettingsPanel } from "@/components/settings/SettingsPanel";
import { ActivityLogPanel } from "@/components/log/ActivityLogPanel";
import { usePreferences } from "@/hooks/usePreferences";

/* ───────────────────────── helpers ───────────────────────── */

function TerminalLine({
  children,
  delay = 0,
}: {
  children: string;
  delay?: number;
}) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(t);
  }, [delay]);

  if (!visible) return null;
  return (
    <div className="mono text-sm sm:text-base slide-up">
      <span className="text-[var(--green-dim)] opacity-50">$</span>{" "}
      <span className="text-[var(--green)]">{children}</span>
    </div>
  );
}

/* ────────────────────── landing page ────────────────────── */

function Landing({ onEnter }: { onEnter: () => void }) {
  const { isConnected } = useAccount();
  const [authLines, setAuthLines] = useState(false);

  /* show extra terminal lines once wallet connects */
  useEffect(() => {
    if (isConnected) {
      const t = setTimeout(() => setAuthLines(true), 400);
      return () => clearTimeout(t);
    }
    setAuthLines(false);
  }, [isConnected]);

  return (
    <div className="min-h-screen flex flex-col">
      <div className="relative z-10 flex flex-col items-center justify-center flex-1 px-4 sm:px-6 py-10 sm:py-16">
        {/* ASCII logo — hidden on very small screens, show text fallback */}
        <div className="mb-6 sm:mb-8 text-center">
          <pre
            className="pixel text-[var(--green)] text-[4.5px] sm:text-[7px] md:text-[10px] lg:text-xs leading-tight hidden sm:block"
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
          {/* Mobile text logo */}
          <h1
            className="pixel text-[var(--green)] text-sm sm:hidden tracking-wider"
            style={{ textShadow: "0 0 20px rgba(0,255,65,0.6)" }}
          >
            POLYBACKER
          </h1>
        </div>

        {/* Terminal window */}
        <div className="max-w-lg w-full glass rounded-none p-0 mb-6 sm:mb-8 overflow-hidden">
          {/* Title bar */}
          <div className="flex items-center gap-2 px-3 sm:px-4 py-2 border-b border-[var(--panel-border)] bg-[rgba(0,255,65,0.05)]">
            <span className="text-[var(--red)] text-[8px]">&#9679;</span>
            <span className="text-[var(--amber)] text-[8px]">&#9679;</span>
            <span className="text-[var(--green)] text-[8px]">&#9679;</span>
            <span className="mono text-xs text-[var(--green-dim)] ml-2">
              polybacker@polygon:~
            </span>
          </div>
          {/* Terminal body */}
          <div className="p-3 sm:p-4 space-y-1">
            <TerminalLine delay={200}>
              polybacker v0.2.0 -- trading terminal
            </TerminalLine>
            <TerminalLine delay={600}>
              init copy_trading_engine... OK
            </TerminalLine>
            <TerminalLine delay={1000}>
              init arbitrage_scanner... OK
            </TerminalLine>
            <TerminalLine delay={1400}>
              init position_tracker... OK
            </TerminalLine>
            <TerminalLine delay={1800}>
              init fund_manager... OK
            </TerminalLine>
            <TerminalLine delay={2200}>
              connecting to polygon mainnet... OK
            </TerminalLine>
            <TerminalLine delay={2600}>all systems nominal</TerminalLine>

            {!isConnected && (
              <div className="mt-3 pt-3 border-t border-[var(--panel-border)]">
                <TerminalLine delay={3000}>
                  awaiting wallet authentication_
                </TerminalLine>
              </div>
            )}

            {isConnected && authLines && (
              <div className="mt-3 pt-3 border-t border-[var(--panel-border)] space-y-1">
                <TerminalLine delay={0}>wallet connected... OK</TerminalLine>
                <TerminalLine delay={400}>
                  session authenticated... OK
                </TerminalLine>
                <TerminalLine delay={800}>
                  access granted -- welcome operator_
                </TerminalLine>
              </div>
            )}
          </div>
        </div>

        {/* Buttons */}
        <div className="mb-8 sm:mb-12 flex flex-col items-center gap-4">
          {!isConnected && <ConnectButton label="[ CONNECT WALLET ]" />}

          {isConnected && (
            <>
              <ConnectButton />
              <button
                onClick={onEnter}
                className="enter-btn glass rounded-none px-8 sm:px-12 py-3 sm:py-4 border border-[var(--green)] text-[var(--green)] pixel text-[10px] sm:text-xs tracking-widest uppercase hover:bg-[rgba(0,255,65,0.15)] transition-all duration-200 pulse-glow"
              >
                {">"} ENTER TERMINAL {"<"}
              </button>
            </>
          )}
        </div>

        {/* Feature cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 max-w-4xl w-full">
          <div className="glass rounded-none p-4 sm:p-5 slide-up">
            <div className="text-[var(--cyan)] pixel text-[9px] sm:text-[10px] mb-2 sm:mb-3">
              [01]
            </div>
            <h3 className="text-[var(--green)] font-bold mb-1 sm:mb-2 uppercase text-xs sm:text-sm tracking-wider">
              Copy Trading
            </h3>
            <p className="text-[10px] sm:text-xs text-[var(--green-dim)] opacity-70 leading-relaxed">
              Follow top traders with per-wallet customization
            </p>
          </div>
          <div
            className="glass rounded-none p-4 sm:p-5 slide-up"
            style={{ animationDelay: "0.1s" }}
          >
            <div className="text-[var(--amber)] pixel text-[9px] sm:text-[10px] mb-2 sm:mb-3">
              [02]
            </div>
            <h3 className="text-[var(--green)] font-bold mb-1 sm:mb-2 uppercase text-xs sm:text-sm tracking-wider">
              Arbitrage
            </h3>
            <p className="text-[10px] sm:text-xs text-[var(--green-dim)] opacity-70 leading-relaxed">
              Scan for pricing inefficiencies and capture profit
            </p>
          </div>
          <div
            className="glass rounded-none p-4 sm:p-5 slide-up"
            style={{ animationDelay: "0.2s" }}
          >
            <div className="text-[var(--magenta)] pixel text-[9px] sm:text-[10px] mb-2 sm:mb-3">
              [03]
            </div>
            <h3 className="text-[var(--green)] font-bold mb-1 sm:mb-2 uppercase text-xs sm:text-sm tracking-wider">
              Positions
            </h3>
            <p className="text-[10px] sm:text-xs text-[var(--green-dim)] opacity-70 leading-relaxed">
              Track open positions with live P&L in real-time
            </p>
          </div>
          <div
            className="glass rounded-none p-4 sm:p-5 slide-up"
            style={{ animationDelay: "0.3s" }}
          >
            <div className="text-[var(--green)] pixel text-[9px] sm:text-[10px] mb-2 sm:mb-3">
              [04]
            </div>
            <h3 className="text-[var(--green)] font-bold mb-1 sm:mb-2 uppercase text-xs sm:text-sm tracking-wider">
              STF Funds
            </h3>
            <p className="text-[10px] sm:text-xs text-[var(--green-dim)] opacity-70 leading-relaxed">
              Invest in curated funds of top-performing traders
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 sm:mt-12 mono text-[10px] sm:text-xs text-[var(--green-dark)] text-center">
          polybacker.com // built on polygon // powered by polymarket
        </div>
      </div>
    </div>
  );
}

/* ──────────────────────── dashboard ─────────────────────── */

function Dashboard({ onExit }: { onExit: () => void }) {
  const { prefs, savePrefs } = usePreferences();
  const [activeTab, setActiveTab] = useState<Tab>("summary");
  const prefsLoaded = useRef(false);

  // Restore saved tab on mount
  useEffect(() => {
    if (prefsLoaded.current) return;
    if (prefs.activeTab) {
      const validTabs: Tab[] = ["summary", "copy", "arb", "positions", "watchlist", "fund", "log", "settings", "admin"];
      if (validTabs.includes(prefs.activeTab as Tab)) {
        setActiveTab(prefs.activeTab as Tab);
        prefsLoaded.current = true;
      }
    }
  }, [prefs]);

  const handleTabChange = useCallback((tab: Tab) => {
    setActiveTab(tab);
    savePrefs({ activeTab: tab });
  }, [savePrefs]);

  return (
    <div className="min-h-screen">
      <div className="relative z-10">
        <Header onLogoClick={onExit} />
        <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
          <TabNav activeTab={activeTab} onTabChange={handleTabChange} />
          {activeTab === "summary" && <SummaryPanel />}
          {activeTab === "copy" && <CopyPanel />}
          {activeTab === "arb" && <ArbPanel />}
          {activeTab === "positions" && <PositionsPanel />}
          {activeTab === "watchlist" && <WatchlistPanel />}
          {activeTab === "fund" && <FundPanel />}
          {activeTab === "log" && <ActivityLogPanel />}
          {activeTab === "settings" && <SettingsPanel />}
          {activeTab === "admin" && <AdminPanel />}
        </main>
      </div>
    </div>
  );
}

/* ──────────────────── page transition ───────────────────── */

type ViewState = "landing" | "transitioning" | "dashboard";

export default function Home() {
  const { isConnected } = useAccount();

  // Auto-restore dashboard if user was previously in it and has a valid token
  const [view, setView] = useState<ViewState>(() => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("polybacker_token");
      const wasInDashboard = localStorage.getItem("polybacker_view") === "dashboard";
      if (token && wasInDashboard) return "dashboard";
    }
    return "landing";
  });

  /* if wallet disconnects while in dashboard, go back */
  useEffect(() => {
    if (!isConnected && view === "dashboard") {
      setView("landing");
      localStorage.removeItem("polybacker_view");
    }
  }, [isConnected, view]);

  // Persist view state
  useEffect(() => {
    if (typeof window !== "undefined") {
      if (view === "dashboard") {
        localStorage.setItem("polybacker_view", "dashboard");
      } else if (view === "landing") {
        localStorage.removeItem("polybacker_view");
      }
    }
  }, [view]);

  const handleEnter = useCallback(() => {
    setView("transitioning");
    /* let the slide-out animation play, then swap view */
    setTimeout(() => setView("dashboard"), 600);
  }, []);

  const handleExit = useCallback(() => {
    setView("landing");
  }, []);

  if (view === "landing") {
    return (
      <div className="page-enter">
        <Landing onEnter={handleEnter} />
      </div>
    );
  }

  if (view === "transitioning") {
    return (
      <div className="transition-screen">
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center space-y-4">
            <div className="mono text-lg sm:text-xl text-[var(--green)]">
              INITIALIZING TERMINAL<span className="blink">_</span>
            </div>
            <div className="w-64 sm:w-80 h-1 bg-[var(--panel-border)] mx-auto overflow-hidden rounded-none">
              <div className="h-full bg-[var(--green)] loading-bar" />
            </div>
            <div className="mono text-xs text-[var(--green-dim)]">
              loading modules...
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-enter">
      <Dashboard onExit={handleExit} />
    </div>
  );
}

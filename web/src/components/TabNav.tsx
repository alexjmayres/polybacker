"use client";

import { useAuth } from "@/hooks/useAuth";

export type Tab = "summary" | "markets" | "copy" | "arb" | "positions" | "watchlist" | "fund" | "log" | "settings" | "admin";

interface TabNavProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

const tabs: { key: Tab; label: string; ownerOnly?: boolean }[] = [
  { key: "summary", label: "[SUMMARY]" },
  { key: "markets", label: "[MARKETS]" },
  { key: "copy", label: "[COPY TRADE]" },
  { key: "arb", label: "[ARBITRAGE]" },
  { key: "positions", label: "[POSITIONS]" },
  { key: "watchlist", label: "[WATCHLIST]" },
  { key: "fund", label: "[STF FUNDS]" },
  { key: "log", label: "[ACTIVITY LOG]" },
  { key: "settings", label: "[SETTINGS]" },
  { key: "admin", label: "[ADMIN]", ownerOnly: true },
];

export function TabNav({ activeTab, onTabChange }: TabNavProps) {
  const { isOwner } = useAuth();

  return (
    <div className="flex gap-1 mb-8 border-b border-[var(--panel-border)] overflow-x-auto scrollbar-hide">
      {tabs
        .filter((tab) => !tab.ownerOnly || isOwner)
        .map((tab) => (
          <button
            key={tab.key}
            onClick={() => onTabChange(tab.key)}
            className={`pb-3 px-3 sm:px-4 font-bold text-[10px] sm:text-xs uppercase tracking-widest transition-all whitespace-nowrap ${
              activeTab === tab.key
                ? "tab-active"
                : "text-[var(--green-dark)] hover:text-[var(--green)]"
            }`}
          >
            {tab.label}
          </button>
        ))}
    </div>
  );
}

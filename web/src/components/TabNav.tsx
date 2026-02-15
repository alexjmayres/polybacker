"use client";

type Tab = "summary" | "copy" | "arb" | "positions" | "fund";

interface TabNavProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

const tabs: { key: Tab; label: string }[] = [
  { key: "summary", label: "[SUMMARY]" },
  { key: "copy", label: "[COPY]" },
  { key: "arb", label: "[ARB]" },
  { key: "positions", label: "[POSITIONS]" },
  { key: "fund", label: "[STF FUNDS]" },
];

export function TabNav({ activeTab, onTabChange }: TabNavProps) {
  return (
    <div className="flex gap-1 mb-8 border-b border-[var(--panel-border)] overflow-x-auto scrollbar-hide">
      {tabs.map((tab) => (
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

"use client";

interface TabNavProps {
  activeTab: "copy" | "arb";
  onTabChange: (tab: "copy" | "arb") => void;
}

export function TabNav({ activeTab, onTabChange }: TabNavProps) {
  return (
    <div className="flex gap-1 mb-8 border-b border-[var(--panel-border)]">
      <button
        onClick={() => onTabChange("copy")}
        className={`pb-3 px-4 font-bold text-xs uppercase tracking-widest transition-all ${
          activeTab === "copy"
            ? "tab-active"
            : "text-[var(--green-dark)] hover:text-[var(--green)]"
        }`}
      >
        [COPY TRADING]
      </button>
      <button
        onClick={() => onTabChange("arb")}
        className={`pb-3 px-4 font-bold text-xs uppercase tracking-widest transition-all ${
          activeTab === "arb"
            ? "tab-active"
            : "text-[var(--green-dark)] hover:text-[var(--green)]"
        }`}
      >
        [ARBITRAGE]
      </button>
    </div>
  );
}

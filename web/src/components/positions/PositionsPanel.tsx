"use client";

import { useQuery } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";

interface Position {
  id: number;
  token_id: string;
  market: string;
  side: string;
  size: number;
  avg_entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  cost_basis: number;
  strategy: string;
  copied_from: string | null;
  opened_at: string;
  last_updated: string;
  status: string;
}

interface PositionSummary {
  open_count: number;
  total_value: number;
  unrealized_pnl: number;
}

export function PositionsPanel() {
  const { data: positions = [], isLoading } = useQuery<Position[]>({
    queryKey: ["positions"],
    queryFn: () => apiJson("/api/positions"),
    refetchInterval: 15000,
  });

  const { data: summary } = useQuery<PositionSummary>({
    queryKey: ["positions-summary"],
    queryFn: () => apiJson("/api/positions/summary"),
    refetchInterval: 15000,
  });

  const timeAgo = (ts: string) => {
    const diff = Date.now() - new Date(ts + "Z").getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    return `${Math.floor(hrs / 24)}d`;
  };

  const formatPnl = (pnl: number) => {
    const sign = pnl >= 0 ? "+" : "";
    return `${sign}$${pnl.toFixed(2)}`;
  };

  const pnlPct = (pnl: number, cost: number) => {
    if (cost <= 0) return "0.0";
    return ((pnl / cost) * 100).toFixed(1);
  };

  const statItems = [
    {
      label: "OPEN POSITIONS",
      value: String(summary?.open_count ?? positions.length),
      color: "text-[var(--green)]",
    },
    {
      label: "TOTAL VALUE",
      value: `$${(summary?.total_value ?? 0).toFixed(2)}`,
      color: "text-[var(--cyan)]",
    },
    {
      label: "UNREALIZED P&L",
      value: formatPnl(summary?.unrealized_pnl ?? 0),
      color:
        (summary?.unrealized_pnl ?? 0) >= 0
          ? "text-[var(--green)]"
          : "text-[var(--red)]",
    },
  ];

  return (
    <div className="space-y-6 slide-up">
      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        {statItems.map((item) => (
          <div key={item.label} className="glass rounded-none p-4 slide-up">
            <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
              {item.label}
            </div>
            <div className={`text-xl sm:text-2xl font-bold mono ${item.color}`}>
              {item.value}
            </div>
          </div>
        ))}
      </div>

      {/* Positions Table */}
      <div className="glass rounded-none p-4 sm:p-5">
        <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
          // OPEN POSITIONS
        </h3>

        {isLoading ? (
          <div className="text-center py-8">
            <span className="mono text-sm text-[var(--green-dim)]">
              LOADING POSITIONS<span className="blink">_</span>
            </span>
          </div>
        ) : positions.length === 0 ? (
          <div className="text-center py-8">
            <span className="mono text-sm text-[var(--green-dark)]">
              no open positions
            </span>
          </div>
        ) : (
          <>
            {/* Desktop header */}
            <div className="hidden lg:grid grid-cols-12 gap-2 text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2 px-3">
              <div className="col-span-3">MARKET</div>
              <div className="col-span-1">SIDE</div>
              <div className="col-span-1">SIZE</div>
              <div className="col-span-1">ENTRY</div>
              <div className="col-span-1">CURRENT</div>
              <div className="col-span-2">P&L</div>
              <div className="col-span-1">TYPE</div>
              <div className="col-span-2">AGE</div>
            </div>

            <div className="space-y-1">
              {positions.map((pos) => (
                <div
                  key={pos.id}
                  className={`bg-[rgba(0,255,65,0.02)] border px-3 py-2 ${
                    pos.unrealized_pnl >= 0
                      ? "border-[rgba(0,255,65,0.08)]"
                      : "border-[rgba(255,51,51,0.08)]"
                  }`}
                >
                  {/* Desktop layout */}
                  <div className="hidden lg:grid grid-cols-12 gap-2 items-center">
                    <div className="col-span-3 mono text-sm text-[var(--green)] truncate">
                      {pos.market || "Unknown"}
                    </div>
                    <div className="col-span-1">
                      <span
                        className={`text-[10px] font-bold px-1.5 py-0.5 ${
                          pos.side === "LONG"
                            ? "text-[var(--green)] border border-[var(--green)]"
                            : "text-[var(--red)] border border-[var(--red)]"
                        }`}
                      >
                        {pos.side}
                      </span>
                    </div>
                    <div className="col-span-1 mono text-sm text-[var(--cyan)]">
                      ${pos.cost_basis.toFixed(2)}
                    </div>
                    <div className="col-span-1 mono text-sm text-[var(--green-dim)]">
                      ${pos.avg_entry_price.toFixed(2)}
                    </div>
                    <div className="col-span-1 mono text-sm text-[var(--green-dim)]">
                      ${pos.current_price.toFixed(2)}
                    </div>
                    <div className="col-span-2">
                      <span
                        className={`mono text-sm font-bold ${
                          pos.unrealized_pnl >= 0
                            ? "text-[var(--green)]"
                            : "text-[var(--red)]"
                        }`}
                      >
                        {formatPnl(pos.unrealized_pnl)}
                      </span>
                      <span
                        className={`mono text-[10px] ml-1 ${
                          pos.unrealized_pnl >= 0
                            ? "text-[var(--green-dim)]"
                            : "text-[var(--red)]"
                        }`}
                      >
                        ({pnlPct(pos.unrealized_pnl, pos.cost_basis)}%)
                      </span>
                    </div>
                    <div className="col-span-1">
                      <span
                        className={`text-[10px] font-bold px-1.5 py-0.5 ${
                          pos.strategy === "copy"
                            ? "text-[var(--cyan)] border border-[var(--cyan)]"
                            : pos.strategy === "arb" || pos.strategy === "arbitrage"
                            ? "text-[var(--amber)] border border-[var(--amber)]"
                            : "text-[var(--magenta)] border border-[var(--magenta)]"
                        }`}
                      >
                        {pos.strategy === "arbitrage" ? "ARB" : pos.strategy.toUpperCase()}
                      </span>
                    </div>
                    <div className="col-span-2 mono text-[10px] text-[var(--green-dark)]">
                      {timeAgo(pos.opened_at)}
                    </div>
                  </div>

                  {/* Mobile layout */}
                  <div className="lg:hidden space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="mono text-sm text-[var(--green)] truncate flex-1 mr-2">
                        {pos.market || "Unknown"}
                      </span>
                      <span
                        className={`text-[10px] font-bold px-1.5 py-0.5 ${
                          pos.side === "LONG"
                            ? "text-[var(--green)] border border-[var(--green)]"
                            : "text-[var(--red)] border border-[var(--red)]"
                        }`}
                      >
                        {pos.side}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="mono text-[10px] text-[var(--green-dark)]">
                          ${pos.cost_basis.toFixed(2)} @ ${pos.avg_entry_price.toFixed(2)}
                        </span>
                        <span className="mono text-[10px] text-[var(--green-dark)]">
                          → ${pos.current_price.toFixed(2)}
                        </span>
                      </div>
                      <span
                        className={`mono text-sm font-bold ${
                          pos.unrealized_pnl >= 0
                            ? "text-[var(--green)]"
                            : "text-[var(--red)]"
                        }`}
                      >
                        {formatPnl(pos.unrealized_pnl)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";

interface TraderPnl {
  address: string;
  alias: string;
  active: boolean;
  followed_since: string;
  trade_count: number;
  total_spent: number;
  executed_spent: number;
  failed_count: number;
  unrealized_pnl: number;
  current_value: number;
  cost_basis: number;
  position_count: number;
  order_mode: string | null;
}

export function TraderPnlTable() {
  const { data: traders = [] } = useQuery<TraderPnl[]>({
    queryKey: ["trader-pnl"],
    queryFn: () => apiJson("/api/copy/traders/pnl"),
    refetchInterval: 30000,
  });

  if (traders.length === 0) return null;

  const truncate = (addr: string) =>
    `${addr.slice(0, 6)}...${addr.slice(-4)}`;

  const formatDate = (d: string) => {
    if (!d) return "—";
    try {
      return new Date(d).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      });
    } catch {
      return d.slice(0, 10);
    }
  };

  // Sort by PNL descending
  const sorted = [...traders].sort(
    (a, b) => b.unrealized_pnl - a.unrealized_pnl
  );

  return (
    <div className="glass rounded-none p-4 sm:p-5 slide-up">
      <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
        // TRADER PNL (SINCE FOLLOWED)
      </h3>

      {/* Desktop header */}
      <div className="hidden lg:grid grid-cols-12 gap-2 text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2 px-3">
        <div className="col-span-3">TRADER</div>
        <div className="col-span-1 text-right">SINCE</div>
        <div className="col-span-1 text-right">TRADES</div>
        <div className="col-span-2 text-right">SPENT</div>
        <div className="col-span-2 text-right">VALUE</div>
        <div className="col-span-2 text-right">PNL</div>
        <div className="col-span-1 text-right">MODE</div>
      </div>

      <div className="space-y-1 max-h-[350px] overflow-y-auto">
        {sorted.map((t) => {
          const pnl = t.unrealized_pnl;
          const pnlPct =
            t.cost_basis > 0
              ? ((t.current_value - t.cost_basis) / t.cost_basis) * 100
              : 0;
          const isPositive = pnl >= 0;

          return (
            <div
              key={t.address}
              className={`border px-3 py-2 ${
                !t.active
                  ? "opacity-40 border-[rgba(255,0,0,0.08)]"
                  : isPositive
                  ? "bg-[rgba(0,255,65,0.02)] border-[rgba(0,255,65,0.08)]"
                  : "bg-[rgba(255,51,51,0.02)] border-[rgba(255,51,51,0.08)]"
              }`}
            >
              {/* Desktop */}
              <div className="hidden lg:grid grid-cols-12 gap-2 items-center">
                <div className="col-span-3 flex items-center gap-2 min-w-0">
                  <span
                    className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${
                      t.active ? "bg-[var(--green)]" : "bg-[var(--red)]"
                    }`}
                  />
                  <span className="mono text-sm text-[var(--cyan)] truncate">
                    {t.alias || truncate(t.address)}
                  </span>
                </div>
                <div className="col-span-1 mono text-[10px] text-[var(--green-dark)] text-right">
                  {formatDate(t.followed_since)}
                </div>
                <div className="col-span-1 mono text-sm text-[var(--green-dim)] text-right">
                  {t.trade_count}
                  {t.failed_count > 0 && (
                    <span className="text-[var(--red)] text-[9px] ml-0.5">
                      ({t.failed_count}F)
                    </span>
                  )}
                </div>
                <div className="col-span-2 mono text-sm text-[var(--amber)] text-right">
                  ${t.executed_spent.toFixed(2)}
                </div>
                <div className="col-span-2 mono text-sm text-[var(--cyan)] text-right">
                  ${t.current_value.toFixed(2)}
                </div>
                <div className="col-span-2 text-right">
                  <span
                    className={`mono text-sm font-bold ${
                      isPositive ? "text-[var(--green)]" : "text-[var(--red)]"
                    }`}
                  >
                    {isPositive ? "+" : ""}${pnl.toFixed(2)}
                  </span>
                  {t.cost_basis > 0 && (
                    <span
                      className={`mono text-[10px] ml-1 ${
                        isPositive
                          ? "text-[var(--green-dim)]"
                          : "text-[var(--red)]"
                      }`}
                    >
                      ({pnlPct >= 0 ? "+" : ""}
                      {pnlPct.toFixed(1)}%)
                    </span>
                  )}
                </div>
                <div className="col-span-1 mono text-[9px] text-right">
                  <span
                    className={`px-1 py-0.5 border rounded-none ${
                      t.order_mode === "market"
                        ? "text-[var(--amber)] border-[var(--amber)]"
                        : "text-[var(--cyan)] border-[var(--cyan)]"
                    }`}
                  >
                    {(t.order_mode || "limit").toUpperCase()}
                  </span>
                </div>
              </div>

              {/* Mobile */}
              <div className="lg:hidden space-y-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 min-w-0 flex-1 mr-2">
                    <span
                      className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${
                        t.active ? "bg-[var(--green)]" : "bg-[var(--red)]"
                      }`}
                    />
                    <span className="mono text-sm text-[var(--cyan)] truncate">
                      {t.alias || truncate(t.address)}
                    </span>
                  </div>
                  <span
                    className={`mono text-sm font-bold shrink-0 ${
                      isPositive ? "text-[var(--green)]" : "text-[var(--red)]"
                    }`}
                  >
                    {isPositive ? "+" : ""}${pnl.toFixed(2)}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-[10px] mono text-[var(--green-dark)]">
                  <span>{t.trade_count} trades</span>
                  <span>${t.executed_spent.toFixed(2)} spent</span>
                  <span>since {formatDate(t.followed_since)}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";
import { PnlChart } from "@/components/PnlChart";

interface CopyStats {
  total_trades: number;
  total_spent: number;
  failed_trades: number;
  daily_spend: number;
  daily_limit: number;
}

interface ArbStats {
  total_trades: number;
  total_spent: number;
  total_expected_profit: number;
  failed_trades: number;
}

interface Trade {
  id: number;
  timestamp: string;
  strategy: string;
  market: string;
  side: string;
  amount: number;
  status: string;
}

interface PositionSummary {
  open_count: number;
  total_value: number;
  unrealized_pnl: number;
}

interface WalletBalances {
  pol_balance: number;
  pol_price_usd: number;
  pol_usd_value: number;
  usdc_e_balance: number;
  usdc_e_usd_value: number;
  total_usd: number;
}

export function SummaryPanel() {
  const { data: copyStats } = useQuery<CopyStats>({
    queryKey: ["copy-stats"],
    queryFn: () => apiJson("/api/copy/stats"),
    refetchInterval: 15000,
  });

  const { data: arbStats } = useQuery<ArbStats>({
    queryKey: ["arb-stats"],
    queryFn: () => apiJson("/api/arb/stats"),
    refetchInterval: 15000,
  });

  const { data: recentTrades = [] } = useQuery<Trade[]>({
    queryKey: ["recent-trades"],
    queryFn: () => apiJson("/api/trades?limit=10"),
    refetchInterval: 15000,
  });

  const { data: posSummary } = useQuery<PositionSummary>({
    queryKey: ["positions-summary"],
    queryFn: () => apiJson("/api/positions/summary"),
    refetchInterval: 15000,
    retry: false,
  });

  const { data: balances } = useQuery<WalletBalances>({
    queryKey: ["wallet-balances"],
    queryFn: () => apiJson("/api/wallet/balances"),
    refetchInterval: 30000,
    retry: false,
  });

  const totalTrades =
    (copyStats?.total_trades ?? 0) + (arbStats?.total_trades ?? 0);
  const totalSpent =
    (copyStats?.total_spent ?? 0) + (arbStats?.total_spent ?? 0);
  const totalProfit = arbStats?.total_expected_profit ?? 0;
  const openPositions = posSummary?.open_count ?? 0;
  const unrealizedPnl = posSummary?.unrealized_pnl ?? 0;

  const statItems = [
    {
      label: "TOTAL TRADES",
      value: String(totalTrades),
      color: "text-[var(--green)]",
    },
    {
      label: "TOTAL VOLUME",
      value: `$${totalSpent.toFixed(2)}`,
      color: "text-[var(--cyan)]",
    },
    {
      label: "EST. PROFIT",
      value: `${totalProfit >= 0 ? "+" : ""}$${totalProfit.toFixed(2)}`,
      color:
        totalProfit >= 0 ? "text-[var(--green)]" : "text-[var(--red)]",
    },
    {
      label: "OPEN POS.",
      value: String(openPositions),
      color: "text-[var(--amber)]",
    },
    {
      label: "UNREAL. P&L",
      value: `${unrealizedPnl >= 0 ? "+" : ""}$${unrealizedPnl.toFixed(2)}`,
      color:
        unrealizedPnl >= 0 ? "text-[var(--green)]" : "text-[var(--red)]",
    },
  ];

  const timeAgo = (ts: string) => {
    const diff = Date.now() - new Date(ts + "Z").getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    return `${Math.floor(hrs / 24)}d`;
  };

  return (
    <div className="space-y-6 slide-up">
      {/* Combined Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
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

      {/* Wallet Balances */}
      {balances && (
        <div className="glass rounded-none p-4 sm:p-5 slide-up">
          <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-3">
            // WALLET BALANCES
          </h3>
          <div className="flex items-end gap-3">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 flex-1">
              <div>
                <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-1">
                  USDCe
                </div>
                <div className="text-lg font-bold mono text-[var(--cyan)]">
                  ${balances.usdc_e_usd_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
                <div className="text-[9px] mono text-[var(--green-dark)]">
                  {balances.usdc_e_balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })} USDCe
                </div>
              </div>
              <div>
                <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-1">
                  POL
                </div>
                <div className="text-lg font-bold mono text-[var(--amber)]">
                  ${balances.pol_usd_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
                <div className="text-[9px] mono text-[var(--green-dark)]">
                  {balances.pol_balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })} POL @ ${balances.pol_price_usd.toFixed(4)}
                </div>
              </div>
              <div className="col-span-2 sm:col-span-1 flex items-center justify-center sm:justify-end">
                <div className="text-center sm:text-right">
                  <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-1">
                    TOTAL
                  </div>
                  <div className="text-2xl sm:text-3xl font-bold mono text-[var(--red)]">
                    ${balances.total_usd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                  <div className="text-[9px] mono text-[var(--green-dark)]">
                    USD
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* PnL Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
            // COPY TRADING P&L
          </div>
          <PnlChart strategy="copy" />
        </div>
        <div>
          <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
            // ARBITRAGE P&L
          </div>
          <PnlChart strategy="arb" />
        </div>
      </div>

      {/* Recent Activity Feed */}
      <div className="glass rounded-none p-4 sm:p-5">
        <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
          // RECENT ACTIVITY
        </h3>
        <div className="space-y-1 max-h-64 overflow-y-auto">
          {recentTrades.length === 0 ? (
            <p className="mono text-sm text-[var(--green-dark)] text-center py-4">
              no trades recorded
            </p>
          ) : (
            recentTrades.map((trade) => (
              <div
                key={trade.id}
                className="flex items-center justify-between bg-[rgba(0,255,65,0.02)] border border-[rgba(0,255,65,0.08)] px-3 py-2"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <span
                    className={`text-[10px] font-bold px-1.5 py-0.5 ${
                      trade.strategy === "copy"
                        ? "text-[var(--cyan)] border border-[var(--cyan)]"
                        : "text-[var(--amber)] border border-[var(--amber)]"
                    }`}
                  >
                    {trade.strategy === "copy" ? "COPY" : "ARB"}
                  </span>
                  <span className="mono text-sm text-[var(--green)] truncate">
                    {trade.market || "Unknown Market"}
                  </span>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span
                    className={`mono text-sm ${
                      trade.side === "BUY"
                        ? "text-[var(--green)]"
                        : "text-[var(--red)]"
                    }`}
                  >
                    {trade.side}
                  </span>
                  <span className="mono text-sm text-[var(--cyan)]">
                    ${trade.amount.toFixed(2)}
                  </span>
                  <span className="mono text-[10px] text-[var(--green-dark)]">
                    {timeAgo(trade.timestamp)}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

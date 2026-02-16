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

interface WalletBalances {
  pol_balance: number;
  pol_price_usd: number;
  pol_usd_value: number;
  usdc_e_balance: number;
  usdc_e_usd_value: number;
  total_usd: number;
}

interface PortfolioPosition {
  title: string;
  outcome: string;
  size: number;
  avgPrice: number;
  curPrice: number;
  cost: number;
  value: number;
  pnl: number;
  pnlPct: number;
  side: string;
}

interface PortfolioSummary {
  total_positions: number;
  total_invested: number;
  total_current_value: number;
  total_pnl: number;
  total_pnl_pct: number;
}

interface PortfolioData {
  positions: PortfolioPosition[];
  trades: unknown[];
  summary: PortfolioSummary;
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

  const { data: balances } = useQuery<WalletBalances>({
    queryKey: ["wallet-balances"],
    queryFn: () => apiJson("/api/wallet/balances"),
    refetchInterval: 30000,
    retry: false,
  });

  const { data: portfolio } = useQuery<PortfolioData>({
    queryKey: ["portfolio"],
    queryFn: () => apiJson("/api/portfolio"),
    refetchInterval: 30000,
    retry: false,
  });

  const totalTrades =
    (copyStats?.total_trades ?? 0) + (arbStats?.total_trades ?? 0);
  const totalSpent =
    (copyStats?.total_spent ?? 0) + (arbStats?.total_spent ?? 0);

  const pmPositions = portfolio?.summary?.total_positions ?? 0;
  const pmInvested = portfolio?.summary?.total_invested ?? 0;
  const pmValue = portfolio?.summary?.total_current_value ?? 0;
  const pmPnl = portfolio?.summary?.total_pnl ?? 0;

  const statItems = [
    {
      label: "POLYMARKET P&L",
      value: `${pmPnl >= 0 ? "+" : ""}$${pmPnl.toFixed(2)}`,
      color: pmPnl >= 0 ? "text-[var(--green)]" : "text-[var(--red)]",
    },
    {
      label: "PORTFOLIO VALUE",
      value: `$${pmValue.toFixed(2)}`,
      color: "text-[var(--cyan)]",
    },
    {
      label: "INVESTED",
      value: `$${pmInvested.toFixed(2)}`,
      color: "text-[var(--amber)]",
    },
    {
      label: "LIVE POSITIONS",
      value: String(pmPositions),
      color: "text-[var(--green)]",
    },
    {
      label: "BOT TRADES",
      value: String(totalTrades),
      color: "text-[var(--magenta)]",
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
      {/* Stats Row */}
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

      {/* Wallet + Polymarket Balances */}
      <div className="glass rounded-none p-4 sm:p-5 slide-up">
        <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-3">
          // WALLET BALANCES
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div>
            <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-1">
              USDCe
            </div>
            <div className="text-lg font-bold mono text-[var(--cyan)]">
              ${(balances?.usdc_e_usd_value ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="text-[9px] mono text-[var(--green-dark)]">
              {(balances?.usdc_e_balance ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })} USDCe
            </div>
          </div>
          <div>
            <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-1">
              POL
            </div>
            <div className="text-lg font-bold mono text-[var(--amber)]">
              ${(balances?.pol_usd_value ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="text-[9px] mono text-[var(--green-dark)]">
              {(balances?.pol_balance ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })} POL @ ${(balances?.pol_price_usd ?? 0).toFixed(4)}
            </div>
          </div>
          <div>
            <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-1">
              POLYMARKET
            </div>
            <div className="text-lg font-bold mono text-[var(--magenta)]">
              ${pmValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="text-[9px] mono text-[var(--green-dark)]">
              {pmPositions} open positions
            </div>
          </div>
          <div className="flex items-center justify-center sm:justify-end">
            <div className="text-center sm:text-right">
              <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-1">
                TOTAL
              </div>
              <div className="text-2xl sm:text-3xl font-bold mono text-[var(--red)]">
                ${((balances?.total_usd ?? 0) + pmValue).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
              <div className="text-[9px] mono text-[var(--green-dark)]">
                USD (wallet + positions)
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Single PnL Chart — all Polymarket activity */}
      <div>
        <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
          // POLYMARKET PERFORMANCE (30D)
        </div>
        <PnlChart strategy="copy" />
      </div>

      {/* Live Polymarket Positions */}
      {portfolio && portfolio.positions.length > 0 && (
        <div className="glass rounded-none p-4 sm:p-5">
          <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
            // POLYMARKET POSITIONS ({portfolio.positions.length})
          </h3>

          {/* Desktop header */}
          <div className="hidden lg:grid grid-cols-12 gap-2 text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2 px-3">
            <div className="col-span-4">MARKET</div>
            <div className="col-span-1">SHARES</div>
            <div className="col-span-1">ENTRY</div>
            <div className="col-span-1">CURRENT</div>
            <div className="col-span-1">COST</div>
            <div className="col-span-1">VALUE</div>
            <div className="col-span-2">P&L</div>
          </div>

          <div className="space-y-1 max-h-[300px] overflow-y-auto">
            {portfolio.positions.map((pos, i) => (
              <div
                key={i}
                className={`border px-3 py-2 ${
                  pos.pnl >= 0
                    ? "bg-[rgba(0,255,65,0.02)] border-[rgba(0,255,65,0.08)]"
                    : "bg-[rgba(255,51,51,0.02)] border-[rgba(255,51,51,0.08)]"
                }`}
              >
                {/* Desktop */}
                <div className="hidden lg:grid grid-cols-12 gap-2 items-center">
                  <div className="col-span-4 mono text-sm text-[var(--green)] truncate">
                    {pos.title || "Unknown"}
                    {pos.outcome && (
                      <span className="text-[var(--cyan)] text-[10px] ml-1">
                        ({pos.outcome})
                      </span>
                    )}
                  </div>
                  <div className="col-span-1 mono text-sm text-[var(--green-dim)]">
                    {pos.size >= 1000 ? `${(pos.size/1000).toFixed(1)}k` : pos.size.toFixed(1)}
                  </div>
                  <div className="col-span-1 mono text-sm text-[var(--green-dim)]">
                    ${pos.avgPrice.toFixed(2)}
                  </div>
                  <div className="col-span-1 mono text-sm text-[var(--green-dim)]">
                    ${pos.curPrice.toFixed(2)}
                  </div>
                  <div className="col-span-1 mono text-sm text-[var(--cyan)]">
                    ${pos.cost.toFixed(2)}
                  </div>
                  <div className="col-span-1 mono text-sm text-[var(--cyan)]">
                    ${pos.value.toFixed(2)}
                  </div>
                  <div className="col-span-2">
                    <span className={`mono text-sm font-bold ${pos.pnl >= 0 ? "text-[var(--green)]" : "text-[var(--red)]"}`}>
                      {pos.pnl >= 0 ? "+" : ""}${pos.pnl.toFixed(2)}
                    </span>
                    <span className={`mono text-[10px] ml-1 ${pos.pnl >= 0 ? "text-[var(--green-dim)]" : "text-[var(--red)]"}`}>
                      ({pos.pnlPct >= 0 ? "+" : ""}{pos.pnlPct.toFixed(1)}%)
                    </span>
                  </div>
                </div>

                {/* Mobile */}
                <div className="lg:hidden space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="mono text-sm text-[var(--green)] truncate flex-1 mr-2">
                      {pos.title || "Unknown"}
                      {pos.outcome && <span className="text-[var(--cyan)] text-[10px]"> ({pos.outcome})</span>}
                    </span>
                    <span className={`mono text-sm font-bold ${pos.pnl >= 0 ? "text-[var(--green)]" : "text-[var(--red)]"}`}>
                      {pos.pnl >= 0 ? "+" : ""}${pos.pnl.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-[10px] mono text-[var(--green-dark)]">
                    <span>{pos.size.toFixed(1)} shares</span>
                    <span>${pos.avgPrice.toFixed(2)} → ${pos.curPrice.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Activity Feed */}
      <div className="glass rounded-none p-4 sm:p-5">
        <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
          // RECENT BOT ACTIVITY
        </h3>
        <div className="space-y-1 max-h-64 overflow-y-auto">
          {recentTrades.length === 0 ? (
            <p className="mono text-sm text-[var(--green-dark)] text-center py-4">
              no bot trades recorded — start the copy or arb engine
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

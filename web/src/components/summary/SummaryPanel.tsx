"use client";

import { useQuery } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";
import { PnlChart } from "@/components/PnlChart";

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
  proxy_wallet: string;
  proxy_usdc_balance: number;
}

export function SummaryPanel() {
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
  ];

  return (
    <div className="space-y-6 slide-up">
      {/* Stats Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
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
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest">
            // WALLET BALANCES
          </h3>
          <a
            href="https://polymarket.com/profile"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[9px] mono font-bold text-black bg-[var(--green)] px-3 py-1 hover:bg-[var(--green-bright)] transition-all tracking-wider"
          >
            DEPOSIT
          </a>
        </div>

        {/* Total Balance — prominent at top */}
        <div className="border border-[rgba(0,255,65,0.1)] bg-[rgba(0,255,65,0.02)] p-4 mb-4">
          <div className="flex items-center justify-between">
            <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest">
              TOTAL BALANCE
            </div>
            <div className="text-2xl sm:text-3xl font-bold mono text-[var(--green)]">
              ${((balances?.total_usd ?? 0) + (portfolio?.proxy_usdc_balance ?? 0) + pmValue).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>
        </div>

        {/* Balance breakdown */}
        <div className="grid grid-cols-3 gap-4">
          <div className="border border-[rgba(0,255,65,0.06)] p-3">
            <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
              USDCe
            </div>
            <div className="text-lg font-bold mono text-[var(--cyan)]">
              ${(balances?.usdc_e_usd_value ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="text-[9px] mono text-[var(--green-dark)] mt-1">
              {(balances?.usdc_e_balance ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })} tokens
            </div>
          </div>
          <div className="border border-[rgba(0,255,65,0.06)] p-3">
            <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
              POL
            </div>
            <div className="text-lg font-bold mono text-[var(--amber)]">
              ${(balances?.pol_usd_value ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="text-[9px] mono text-[var(--green-dark)] mt-1">
              {(balances?.pol_balance ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} @ ${(balances?.pol_price_usd ?? 0).toFixed(4)}
            </div>
          </div>
          <div className="border border-[rgba(0,255,65,0.06)] p-3">
            <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
              PM TRADING
            </div>
            <div className="text-lg font-bold mono text-[var(--magenta)]">
              ${(portfolio?.proxy_usdc_balance ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="text-[9px] mono text-[var(--green-dark)] mt-1">
              {pmPositions > 0 ? `${pmPositions} positions` : "available"}
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
                    <span>${pos.avgPrice.toFixed(2)} &rarr; ${pos.curPrice.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

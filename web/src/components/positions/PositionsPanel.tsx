"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiJson, apiFetch } from "@/lib/api";
import { usePreferences } from "@/hooks/usePreferences";

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

interface ActionResult {
  message: string;
  closed?: number;
  redeemed?: number;
  failed?: number;
  skipped?: number;
  errors?: string[];
}

interface PortfolioTrade {
  id: string;
  timestamp: string;
  market: string;
  outcome: string;
  side: string;
  size: number;
  price: number;
  amount: number;
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

interface PortfolioData {
  positions: PortfolioPosition[];
  trades: PortfolioTrade[];
  summary: {
    total_positions: number;
    total_invested: number;
    total_current_value: number;
    total_pnl: number;
    total_pnl_pct: number;
  };
}

const REFRESH_OPTIONS = [
  { label: "5 MIN", value: 5 * 60 * 1000 },
  { label: "15 MIN", value: 15 * 60 * 1000 },
  { label: "30 MIN", value: 30 * 60 * 1000 },
  { label: "1 HOUR", value: 60 * 60 * 1000 },
  { label: "3 HOURS", value: 3 * 60 * 60 * 1000 },
  { label: "6 HOURS", value: 6 * 60 * 60 * 1000 },
] as const;

export function PositionsPanel() {
  const queryClient = useQueryClient();
  const { prefs, savePrefs } = usePreferences();
  const [confirmClose, setConfirmClose] = useState(false);
  const [autoRedeem, setAutoRedeem] = useState(false);
  const [redeemInterval, setRedeemInterval] = useState(REFRESH_OPTIONS[1].value); // 15 min default
  const [showIntervalDropdown, setShowIntervalDropdown] = useState(false);
  const [prefsLoaded, setPrefsLoaded] = useState(false);

  // Load persisted prefs on mount
  useEffect(() => {
    if (prefsLoaded) return;
    if (prefs.autoRedeem !== undefined) {
      setAutoRedeem(prefs.autoRedeem);
    }
    if (prefs.redeemInterval !== undefined) {
      setRedeemInterval(prefs.redeemInterval);
    }
    if (prefs.autoRedeem !== undefined || prefs.redeemInterval !== undefined) {
      setPrefsLoaded(true);
    }
  }, [prefs, prefsLoaded]);

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

  const { data: portfolio } = useQuery<PortfolioData>({
    queryKey: ["portfolio"],
    queryFn: () => apiJson("/api/portfolio"),
    refetchInterval: 30000,
    retry: false,
  });

  // Auto-redeem query — only active when toggle is on
  useQuery({
    queryKey: ["auto-redeem"],
    queryFn: async () => {
      const result = await apiJson<ActionResult>("/api/positions/redeem-all", {
        method: "POST",
      });
      if (result.redeemed && result.redeemed > 0) {
        queryClient.invalidateQueries({ queryKey: ["positions"] });
        queryClient.invalidateQueries({ queryKey: ["positions-summary"] });
      }
      return result;
    },
    refetchInterval: autoRedeem ? redeemInterval : false,
    enabled: autoRedeem,
    retry: false,
  });

  const closeAllMutation = useMutation({
    mutationFn: () =>
      apiJson<ActionResult>("/api/positions/close-all", { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      queryClient.invalidateQueries({ queryKey: ["positions-summary"] });
      setConfirmClose(false);
    },
    onError: () => setConfirmClose(false),
  });

  const redeemAllMutation = useMutation({
    mutationFn: () =>
      apiJson<ActionResult>("/api/positions/redeem-all", { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      queryClient.invalidateQueries({ queryKey: ["positions-summary"] });
    },
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

  const currentIntervalLabel =
    REFRESH_OPTIONS.find((o) => o.value === redeemInterval)?.label ?? "15 MIN";

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

      {/* Action Buttons */}
      <div className="glass rounded-none p-4 sm:p-5">
          <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
            // POSITION CONTROLS
          </h3>

          <div className="flex flex-wrap items-center gap-3">
            {/* Close All Positions — big red button */}
            {!confirmClose ? (
              <button
                onClick={() => setConfirmClose(true)}
                disabled={positions.length === 0 || closeAllMutation.isPending}
                className="px-4 py-2.5 border-2 border-[var(--red)] text-[var(--red)] font-bold mono text-sm
                  hover:bg-[var(--red)] hover:text-black transition-colors uppercase tracking-wider
                  disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-[var(--red)]"
              >
                CLOSE ALL POSITIONS
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <span className="mono text-[10px] text-[var(--red)] blink">
                  CONFIRM CLOSE ALL?
                </span>
                <button
                  onClick={() => closeAllMutation.mutate()}
                  disabled={closeAllMutation.isPending}
                  className="px-3 py-2 bg-[var(--red)] text-black font-bold mono text-sm
                    hover:brightness-110 transition-colors uppercase"
                >
                  {closeAllMutation.isPending ? "CLOSING..." : "YES, CLOSE ALL"}
                </button>
                <button
                  onClick={() => setConfirmClose(false)}
                  className="px-3 py-2 border border-[var(--green-dark)] text-[var(--green-dark)] mono text-sm
                    hover:border-[var(--green)] hover:text-[var(--green)] transition-colors uppercase"
                >
                  CANCEL
                </button>
              </div>
            )}

            {/* Redeem All */}
            <button
              onClick={() => redeemAllMutation.mutate()}
              disabled={positions.length === 0 || redeemAllMutation.isPending}
              className="px-4 py-2.5 border-2 border-[var(--amber)] text-[var(--amber)] font-bold mono text-sm
                hover:bg-[var(--amber)] hover:text-black transition-colors uppercase tracking-wider
                disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-[var(--amber)]"
            >
              {redeemAllMutation.isPending ? "REDEEMING..." : "REDEEM ALL"}
            </button>

            {/* Divider */}
            <div className="hidden sm:block w-px h-8 bg-[rgba(0,255,65,0.15)]" />

            {/* Auto-Redeem Toggle */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => {
                  const next = !autoRedeem;
                  setAutoRedeem(next);
                  savePrefs({ autoRedeem: next });
                }}
                className="flex items-center gap-2"
              >
                <div
                  className={`w-8 h-4 rounded-full relative transition-colors ${
                    autoRedeem
                      ? "bg-[var(--amber)]"
                      : "bg-[rgba(0,255,65,0.15)]"
                  }`}
                >
                  <div
                    className={`absolute top-0.5 w-3 h-3 rounded-full transition-all ${
                      autoRedeem
                        ? "left-4 bg-black"
                        : "left-0.5 bg-[var(--green-dark)]"
                    }`}
                  />
                </div>
                <span
                  className={`mono text-[10px] uppercase tracking-wider ${
                    autoRedeem ? "text-[var(--amber)]" : "text-[var(--green-dark)]"
                  }`}
                >
                  AUTO-REDEEM
                </span>
              </button>

              {/* Interval Dropdown */}
              <div className="relative">
                <button
                  onClick={() => setShowIntervalDropdown(!showIntervalDropdown)}
                  disabled={!autoRedeem}
                  className={`px-2 py-1 border mono text-[10px] uppercase tracking-wider transition-colors
                    ${
                      autoRedeem
                        ? "border-[var(--amber)] text-[var(--amber)] hover:bg-[rgba(255,176,0,0.1)]"
                        : "border-[rgba(0,255,65,0.15)] text-[var(--green-dark)] cursor-not-allowed"
                    }`}
                >
                  {currentIntervalLabel} ▾
                </button>
                {showIntervalDropdown && autoRedeem && (
                  <div className="absolute top-full left-0 mt-1 z-50 border border-[var(--amber)] bg-black min-w-[100px]">
                    {REFRESH_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => {
                          setRedeemInterval(opt.value);
                          setShowIntervalDropdown(false);
                          savePrefs({ redeemInterval: opt.value });
                        }}
                        className={`block w-full text-left px-3 py-1.5 mono text-[10px] uppercase tracking-wider transition-colors
                          hover:bg-[rgba(255,176,0,0.15)] ${
                            opt.value === redeemInterval
                              ? "text-[var(--amber)] bg-[rgba(255,176,0,0.1)]"
                              : "text-[var(--green)]"
                          }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Status Messages */}
          {closeAllMutation.isSuccess && (
            <div className="mt-3 mono text-[10px] text-[var(--green)]">
              {closeAllMutation.data.message}
            </div>
          )}
          {closeAllMutation.isError && (
            <div className="mt-3 mono text-[10px] text-[var(--red)]">
              ERROR: {(closeAllMutation.error as Error).message}
            </div>
          )}
          {redeemAllMutation.isSuccess && (
            <div className="mt-3 mono text-[10px] text-[var(--amber)]">
              {redeemAllMutation.data.message}
            </div>
          )}
          {redeemAllMutation.isError && (
            <div className="mt-3 mono text-[10px] text-[var(--red)]">
              ERROR: {(redeemAllMutation.error as Error).message}
            </div>
          )}
          {autoRedeem && (
            <div className="mt-3 mono text-[10px] text-[var(--amber)]">
              AUTO-REDEEM ACTIVE — checking every {currentIntervalLabel}
            </div>
          )}
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

      {/* Polymarket Live Positions */}
      {portfolio && portfolio.positions.length > 0 && (
        <div className="glass rounded-none p-4 sm:p-5">
          <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
            // POLYMARKET LIVE POSITIONS ({portfolio.positions.length})
          </h3>

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
                <div className="hidden lg:grid grid-cols-12 gap-2 items-center">
                  <div className="col-span-4 mono text-sm text-[var(--green)] truncate">
                    {pos.title || "Unknown"}
                    {pos.outcome && (
                      <span className="text-[var(--cyan)] text-[10px] ml-1">({pos.outcome})</span>
                    )}
                  </div>
                  <div className="col-span-1 mono text-sm text-[var(--green-dim)]">
                    {pos.size >= 1000 ? `${(pos.size / 1000).toFixed(1)}k` : pos.size.toFixed(1)}
                  </div>
                  <div className="col-span-1 mono text-sm text-[var(--green-dim)]">${pos.avgPrice.toFixed(2)}</div>
                  <div className="col-span-1 mono text-sm text-[var(--green-dim)]">${pos.curPrice.toFixed(2)}</div>
                  <div className="col-span-1 mono text-sm text-[var(--cyan)]">${pos.cost.toFixed(2)}</div>
                  <div className="col-span-1 mono text-sm text-[var(--cyan)]">${pos.value.toFixed(2)}</div>
                  <div className="col-span-2">
                    <span className={`mono text-sm font-bold ${pos.pnl >= 0 ? "text-[var(--green)]" : "text-[var(--red)]"}`}>
                      {pos.pnl >= 0 ? "+" : ""}${pos.pnl.toFixed(2)}
                    </span>
                    <span className={`mono text-[10px] ml-1 ${pos.pnl >= 0 ? "text-[var(--green-dim)]" : "text-[var(--red)]"}`}>
                      ({pos.pnlPct >= 0 ? "+" : ""}{pos.pnlPct.toFixed(1)}%)
                    </span>
                  </div>
                </div>
                <div className="lg:hidden space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="mono text-sm text-[var(--green)] truncate flex-1 mr-2">
                      {pos.title || "Unknown"}
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

      {/* Trade History */}
      <div className="glass rounded-none p-4 sm:p-5">
        <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
          // TRADE HISTORY (POLYMARKET)
        </h3>

        {!portfolio || portfolio.trades.length === 0 ? (
          <div className="text-center py-8">
            <span className="mono text-sm text-[var(--green-dark)]">
              no trade history found on Polymarket
            </span>
          </div>
        ) : (
          <>
            <div className="hidden lg:grid grid-cols-12 gap-2 text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2 px-3">
              <div className="col-span-3">MARKET</div>
              <div className="col-span-2">OUTCOME</div>
              <div className="col-span-1">SIDE</div>
              <div className="col-span-1">SHARES</div>
              <div className="col-span-1">PRICE</div>
              <div className="col-span-2">AMOUNT</div>
              <div className="col-span-2">TIME</div>
            </div>

            <div className="space-y-1 max-h-[400px] overflow-y-auto">
              {portfolio.trades.map((trade, i) => (
                <div
                  key={trade.id || i}
                  className={`border px-3 py-2 ${
                    trade.side === "BUY"
                      ? "bg-[rgba(0,255,65,0.02)] border-[rgba(0,255,65,0.08)]"
                      : "bg-[rgba(255,51,51,0.02)] border-[rgba(255,51,51,0.08)]"
                  }`}
                >
                  {/* Desktop */}
                  <div className="hidden lg:grid grid-cols-12 gap-2 items-center">
                    <div className="col-span-3 mono text-sm text-[var(--green)] truncate">
                      {trade.market || "Unknown"}
                    </div>
                    <div className="col-span-2 mono text-[10px] text-[var(--cyan)] truncate">
                      {trade.outcome || "-"}
                    </div>
                    <div className="col-span-1">
                      <span
                        className={`text-[10px] font-bold px-1.5 py-0.5 ${
                          trade.side === "BUY"
                            ? "text-[var(--green)] border border-[var(--green)]"
                            : "text-[var(--red)] border border-[var(--red)]"
                        }`}
                      >
                        {trade.side}
                      </span>
                    </div>
                    <div className="col-span-1 mono text-sm text-[var(--green-dim)]">
                      {trade.size >= 1000 ? `${(trade.size / 1000).toFixed(1)}k` : trade.size.toFixed(1)}
                    </div>
                    <div className="col-span-1 mono text-sm text-[var(--green-dim)]">
                      ${trade.price.toFixed(2)}
                    </div>
                    <div className="col-span-2 mono text-sm text-[var(--cyan)] font-bold">
                      ${trade.amount.toFixed(2)}
                    </div>
                    <div className="col-span-2 mono text-[10px] text-[var(--green-dark)]">
                      {trade.timestamp ? timeAgo(trade.timestamp) : "-"}
                    </div>
                  </div>

                  {/* Mobile */}
                  <div className="lg:hidden space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="mono text-sm text-[var(--green)] truncate flex-1 mr-2">
                        {trade.market || "Unknown"}
                      </span>
                      <span
                        className={`text-[10px] font-bold px-1.5 py-0.5 ${
                          trade.side === "BUY"
                            ? "text-[var(--green)] border border-[var(--green)]"
                            : "text-[var(--red)] border border-[var(--red)]"
                        }`}
                      >
                        {trade.side}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-[10px] mono text-[var(--green-dark)]">
                        <span>{trade.size.toFixed(1)} @ ${trade.price.toFixed(2)}</span>
                        {trade.outcome && <span className="text-[var(--cyan)]">{trade.outcome}</span>}
                      </div>
                      <span className="mono text-sm text-[var(--cyan)] font-bold">
                        ${trade.amount.toFixed(2)}
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

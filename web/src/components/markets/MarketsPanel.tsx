"use client";

import { useState, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiJson, apiFetch } from "@/lib/api";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface Market {
  id: string;
  question: string;
  slug: string;
  image: string;
  category: string;
  end_date: string;
  outcomes: string[];   // ["Yes", "No"]
  prices: number[];     // [0.65, 0.35]
  tokens: string[];     // [token_id_yes, token_id_no]
  volume_24h: number;
  volume_total: number;
  liquidity: number;
}

interface OrderBook {
  order_book: unknown;
  midpoint: number;
  spread: number;
}

interface TradePayload {
  token_id: string;
  side: "BUY" | "SELL";
  amount: number;
  order_type: "market" | "limit";
  price?: number;
  size?: number;
  market?: string;
}

interface TradeResult {
  status: string;
  message?: string;
  error?: string;
  order?: unknown;
}

interface RecentTrade {
  id: number;
  timestamp: string;
  market: string;
  side: string;
  amount: number;
  status: string;
  notes: string | null;
}

type SortOption = "volume24hr" | "liquidity" | "newest";

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatUsd(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}K`;
  return `$${n.toFixed(2)}`;
}

function priceColor(price: number): string {
  return price >= 0.5 ? "text-[var(--green)]" : "text-[var(--red)]";
}

function truncate(s: string | null, len: number): string {
  if (!s) return "--";
  return s.length > len ? s.slice(0, len) + "..." : s;
}

/* ------------------------------------------------------------------ */
/*  Debounce hook                                                      */
/* ------------------------------------------------------------------ */

function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export function MarketsPanel() {
  const queryClient = useQueryClient();

  /* ---- Search + sort state ---- */
  const [searchInput, setSearchInput] = useState("");
  const [sort, setSort] = useState<SortOption>("volume24hr");
  const debouncedSearch = useDebouncedValue(searchInput, 500);

  /* ---- Selected market (expanded trade panel) ---- */
  const [selectedMarketId, setSelectedMarketId] = useState<string | null>(null);

  /* ---- Recent manual trades (local state for this session) ---- */
  const [recentTrades, setRecentTrades] = useState<RecentTrade[]>([]);

  /* -------------------------------------------------------------- */
  /*  Search query                                                   */
  /* -------------------------------------------------------------- */

  const {
    data: markets = [],
    isLoading: marketsLoading,
    error: marketsError,
  } = useQuery<Market[]>({
    queryKey: ["markets-search", debouncedSearch, sort],
    queryFn: () => {
      const params = new URLSearchParams({
        limit: "20",
        sort,
      });
      if (debouncedSearch) params.set("q", debouncedSearch);
      return apiJson(`/api/markets/search?${params}`);
    },
    refetchInterval: 30000,
    retry: 1,
  });

  const selectedMarket = markets.find((m) => m.id === selectedMarketId) ?? null;

  /* -------------------------------------------------------------- */
  /*  Render                                                         */
  /* -------------------------------------------------------------- */

  return (
    <div className="space-y-6 slide-up">
      {/* ---- Search + Sort Row ---- */}
      <div className="glass rounded-none p-4 sm:p-5 slide-up">
        <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
          // MARKET SEARCH
        </h3>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1 relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--green-dark)] mono text-xs">
              &gt;
            </span>
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  queryClient.invalidateQueries({
                    queryKey: ["markets-search"],
                  });
                }
              }}
              placeholder="search markets..."
              className="w-full bg-[rgba(0,255,65,0.03)] border border-[rgba(0,255,65,0.12)] text-[var(--green)] placeholder-[var(--green-dark)] mono text-sm px-7 py-2.5 rounded-none focus:outline-none focus:border-[var(--green)] transition-colors"
            />
            {marketsLoading && (
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--green-dark)] mono text-[10px] blink">
                _
              </span>
            )}
          </div>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortOption)}
            className="bg-[rgba(0,255,65,0.03)] border border-[rgba(0,255,65,0.12)] text-[var(--green)] mono text-xs px-3 py-2.5 rounded-none focus:outline-none focus:border-[var(--green)] transition-colors cursor-pointer"
          >
            <option value="volume24hr">SORT: VOLUME 24H</option>
            <option value="liquidity">SORT: LIQUIDITY</option>
            <option value="newest">SORT: NEWEST</option>
          </select>
        </div>
      </div>

      {/* ---- Error state ---- */}
      {marketsError && (
        <div className="glass rounded-none p-4 border border-[rgba(255,51,51,0.2)]">
          <div className="text-xs mono text-[var(--red)]">
            ERROR: {(marketsError as Error).message || "Failed to fetch markets"}
          </div>
        </div>
      )}

      {/* ---- Markets Grid ---- */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {marketsLoading && markets.length === 0
          ? Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="glass rounded-none p-4 border border-[rgba(0,255,65,0.08)] animate-pulse"
              >
                <div className="h-4 bg-[rgba(0,255,65,0.06)] mb-3 w-3/4" />
                <div className="h-3 bg-[rgba(0,255,65,0.04)] mb-2 w-1/2" />
                <div className="h-3 bg-[rgba(0,255,65,0.04)] w-1/3" />
              </div>
            ))
          : markets.map((market) => (
              <MarketCard
                key={market.id}
                market={market}
                isSelected={selectedMarketId === market.id}
                onSelect={() =>
                  setSelectedMarketId(
                    selectedMarketId === market.id ? null : market.id
                  )
                }
              />
            ))}
      </div>

      {!marketsLoading && markets.length === 0 && (
        <div className="glass rounded-none p-8 text-center">
          <div className="mono text-sm text-[var(--green-dark)]">
            -- no markets found --
          </div>
        </div>
      )}

      {/* ---- Expanded Trade Panel ---- */}
      {selectedMarket && (
        <TradePanel
          market={selectedMarket}
          onClose={() => setSelectedMarketId(null)}
          onTradeComplete={(trade) => {
            setRecentTrades((prev) => [trade, ...prev].slice(0, 20));
          }}
        />
      )}

      {/* ---- Recent Manual Trades ---- */}
      {recentTrades.length > 0 && (
        <RecentTradesTable trades={recentTrades} />
      )}
    </div>
  );
}

/* ================================================================== */
/*  MarketCard                                                         */
/* ================================================================== */

function MarketCard({
  market,
  isSelected,
  onSelect,
}: {
  market: Market;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const yesPrice = market.prices?.[0] ?? 0;
  const noPrice = market.prices?.[1] ?? 0;

  return (
    <button
      onClick={onSelect}
      className={`glass rounded-none p-4 text-left w-full transition-all border ${
        isSelected
          ? "border-[var(--green)] bg-[rgba(0,255,65,0.04)]"
          : "border-[rgba(0,255,65,0.08)] hover:border-[rgba(0,255,65,0.2)] hover:bg-[rgba(0,255,65,0.02)]"
      }`}
    >
      {/* Category tag */}
      {market.category && (
        <div className="text-[9px] mono uppercase tracking-widest text-[var(--magenta)] mb-2">
          {market.category}
        </div>
      )}

      {/* Question */}
      <div className="mono text-sm text-[var(--green)] mb-3 leading-snug">
        {market.question}
      </div>

      {/* Prices */}
      <div className="flex items-center gap-4 mb-3">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] mono text-[var(--green-dark)] uppercase">
            YES
          </span>
          <span className={`mono text-sm font-bold ${priceColor(yesPrice)}`}>
            {(yesPrice * 100).toFixed(1)}%
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] mono text-[var(--green-dark)] uppercase">
            NO
          </span>
          <span className={`mono text-sm font-bold ${priceColor(noPrice)}`}>
            {(noPrice * 100).toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Volume + Liquidity */}
      <div className="flex items-center gap-4 text-[10px] mono text-[var(--green-dark)]">
        <span>
          24H VOL:{" "}
          <span className="text-[var(--cyan)]">
            {formatUsd(market.volume_24h ?? 0)}
          </span>
        </span>
        <span>
          LIQ:{" "}
          <span className="text-[var(--cyan)]">
            {formatUsd(market.liquidity ?? 0)}
          </span>
        </span>
      </div>
    </button>
  );
}

/* ================================================================== */
/*  TradePanel (expanded)                                              */
/* ================================================================== */

function TradePanel({
  market,
  onClose,
  onTradeComplete,
}: {
  market: Market;
  onClose: () => void;
  onTradeComplete: (trade: RecentTrade) => void;
}) {
  const queryClient = useQueryClient();

  /* ---- Trade form state ---- */
  const [outcomeIdx, setOutcomeIdx] = useState(0); // 0 = Yes, 1 = No
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [orderType, setOrderType] = useState<"market" | "limit">("market");
  const [amountStr, setAmountStr] = useState("");
  const [limitPriceStr, setLimitPriceStr] = useState("");
  const [tradeError, setTradeError] = useState<string | null>(null);
  const [tradeSuccess, setTradeSuccess] = useState<string | null>(null);

  const amount = parseFloat(amountStr) || 0;
  const limitPrice = parseFloat(limitPriceStr) || 0;

  const tokenId = market.tokens?.[outcomeIdx] ?? "";
  const currentPrice = market.prices?.[outcomeIdx] ?? 0;

  /* ---- Order book query ---- */
  const { data: orderbook } = useQuery<OrderBook>({
    queryKey: ["orderbook", market.id, tokenId],
    queryFn: () =>
      apiJson(
        `/api/markets/${market.id}/orderbook?token_id=${tokenId}`
      ),
    enabled: !!tokenId,
    refetchInterval: 10000,
    retry: 1,
  });

  /* ---- Estimated shares ---- */
  const effectivePrice =
    orderType === "limit" && limitPrice > 0
      ? limitPrice
      : orderbook?.midpoint ?? currentPrice;

  const estimatedShares =
    effectivePrice > 0 ? amount / effectivePrice : 0;

  /* Auto-calculated size for limit orders */
  const limitSize =
    orderType === "limit" && limitPrice > 0 && amount > 0
      ? amount / limitPrice
      : 0;

  /* ---- Trade mutation ---- */
  const tradeMutation = useMutation({
    mutationFn: async (payload: TradePayload) => {
      const res = await apiFetch("/api/markets/trade", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || `Trade failed: ${res.status}`);
      }
      return data as TradeResult;
    },
    onSuccess: (data) => {
      setTradeSuccess(data.message || "Trade submitted successfully");
      setTradeError(null);
      setAmountStr("");
      setLimitPriceStr("");
      queryClient.invalidateQueries({ queryKey: ["markets-search"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      queryClient.invalidateQueries({ queryKey: ["wallet-balances"] });

      onTradeComplete({
        id: Date.now(),
        timestamp: new Date().toISOString(),
        market: market.question,
        side: `${side} ${market.outcomes?.[outcomeIdx] ?? "?"}`,
        amount,
        status: data.status || "submitted",
        notes: null,
      });
    },
    onError: (err: Error) => {
      setTradeError(err.message);
      setTradeSuccess(null);
    },
  });

  const handleTrade = useCallback(() => {
    if (!tokenId || amount <= 0) return;
    setTradeError(null);
    setTradeSuccess(null);

    const payload: TradePayload = {
      token_id: tokenId,
      side,
      amount,
      order_type: orderType,
      market: market.question,
    };

    if (orderType === "limit") {
      payload.price = limitPrice;
      payload.size = limitSize;
    }

    tradeMutation.mutate(payload);
  }, [tokenId, side, amount, orderType, limitPrice, limitSize, market.question, tradeMutation]);

  const canTrade =
    tokenId && amount > 0 && (orderType === "market" || limitPrice > 0);

  return (
    <div className="glass rounded-none p-4 sm:p-5 slide-up border border-[var(--green)]">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
            // TRADE
          </div>
          <div className="mono text-base sm:text-lg text-[var(--green)] leading-snug">
            {market.question}
          </div>
          {market.category && (
            <div className="text-[9px] mono uppercase tracking-widest text-[var(--magenta)] mt-1">
              {market.category}
            </div>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-[var(--green-dark)] hover:text-[var(--green)] mono text-sm shrink-0 transition-colors"
        >
          [X]
        </button>
      </div>

      {/* Orderbook info */}
      {orderbook && (
        <div className="flex items-center gap-4 text-[10px] mono text-[var(--green-dark)] mb-4 pb-3 border-b border-[rgba(0,255,65,0.08)]">
          <span>
            MIDPOINT:{" "}
            <span className="text-[var(--cyan)]">
              {orderbook.midpoint?.toFixed(4)}
            </span>
          </span>
          <span>
            SPREAD:{" "}
            <span className="text-[var(--amber)]">
              {orderbook.spread?.toFixed(4)}
            </span>
          </span>
        </div>
      )}

      {/* Outcome toggle (Yes / No) */}
      <div className="mb-4">
        <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
          OUTCOME
        </div>
        <div className="flex gap-2">
          {(market.outcomes ?? ["Yes", "No"]).map((outcome, idx) => {
            const price = market.prices?.[idx] ?? 0;
            const isActive = outcomeIdx === idx;
            return (
              <button
                key={outcome}
                onClick={() => setOutcomeIdx(idx)}
                className={`flex-1 border mono text-sm py-2.5 px-4 rounded-none font-bold uppercase tracking-wider transition-all ${
                  isActive
                    ? idx === 0
                      ? "border-[var(--green)] bg-[var(--green)] text-black"
                      : "border-[var(--red)] bg-[var(--red)] text-black"
                    : "border-[rgba(0,255,65,0.12)] text-[var(--green-dim)] hover:border-[rgba(0,255,65,0.3)]"
                }`}
              >
                {outcome} ({(price * 100).toFixed(1)}%)
              </button>
            );
          })}
        </div>
      </div>

      {/* Side (BUY / SELL) */}
      <div className="mb-4">
        <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
          SIDE
        </div>
        <div className="flex gap-2">
          {(["BUY", "SELL"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSide(s)}
              className={`flex-1 border mono text-sm py-2 px-4 rounded-none font-bold uppercase tracking-wider transition-all ${
                side === s
                  ? s === "BUY"
                    ? "border-[var(--green)] bg-[var(--green)] text-black"
                    : "border-[var(--red)] bg-[var(--red)] text-black"
                  : "border-[rgba(0,255,65,0.12)] text-[var(--green-dim)] hover:border-[rgba(0,255,65,0.3)]"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Order type toggle */}
      <div className="mb-4">
        <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
          ORDER TYPE
        </div>
        <div className="flex gap-2">
          {(["market", "limit"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setOrderType(t)}
              className={`flex-1 border mono text-xs py-2 px-4 rounded-none font-bold uppercase tracking-wider transition-all ${
                orderType === t
                  ? "border-[var(--cyan)] bg-[var(--cyan)] text-black"
                  : "border-[rgba(0,255,65,0.12)] text-[var(--green-dim)] hover:border-[rgba(0,255,65,0.3)]"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Amount input */}
      <div className="mb-4">
        <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
          AMOUNT (USDC)
        </div>
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--green-dark)] mono text-sm">
            $
          </span>
          <input
            type="number"
            min="0"
            step="0.01"
            value={amountStr}
            onChange={(e) => setAmountStr(e.target.value)}
            placeholder="0.00"
            className="w-full bg-[rgba(0,255,65,0.03)] border border-[rgba(0,255,65,0.12)] text-[var(--green)] placeholder-[var(--green-dark)] mono text-sm pl-7 pr-3 py-2.5 rounded-none focus:outline-none focus:border-[var(--green)] transition-colors"
          />
        </div>
      </div>

      {/* Limit price + size (only for limit orders) */}
      {orderType === "limit" && (
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div>
            <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
              LIMIT PRICE
            </div>
            <input
              type="number"
              min="0"
              max="1"
              step="0.01"
              value={limitPriceStr}
              onChange={(e) => setLimitPriceStr(e.target.value)}
              placeholder="0.00"
              className="w-full bg-[rgba(0,255,65,0.03)] border border-[rgba(0,255,65,0.12)] text-[var(--green)] placeholder-[var(--green-dark)] mono text-sm px-3 py-2.5 rounded-none focus:outline-none focus:border-[var(--green)] transition-colors"
            />
          </div>
          <div>
            <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
              SIZE (AUTO)
            </div>
            <div className="bg-[rgba(0,255,65,0.03)] border border-[rgba(0,255,65,0.06)] text-[var(--green-dim)] mono text-sm px-3 py-2.5">
              {limitSize > 0 ? limitSize.toFixed(2) : "--"}
            </div>
          </div>
        </div>
      )}

      {/* Estimated shares */}
      <div className="border border-[rgba(0,255,65,0.08)] bg-[rgba(0,255,65,0.02)] p-3 mb-4">
        <div className="flex items-center justify-between">
          <span className="text-[10px] mono text-[var(--green-dark)] uppercase tracking-widest">
            EST. SHARES
          </span>
          <span className="mono text-sm font-bold text-[var(--cyan)]">
            {estimatedShares > 0 ? estimatedShares.toFixed(2) : "--"}
          </span>
        </div>
        <div className="flex items-center justify-between mt-1">
          <span className="text-[10px] mono text-[var(--green-dark)] uppercase tracking-widest">
            EFF. PRICE
          </span>
          <span className="mono text-sm text-[var(--green-dim)]">
            {effectivePrice > 0 ? `$${effectivePrice.toFixed(4)}` : "--"}
          </span>
        </div>
      </div>

      {/* Error / Success messages */}
      {tradeError && (
        <div className="border border-[rgba(255,51,51,0.2)] bg-[rgba(255,51,51,0.04)] p-3 mb-4">
          <div className="text-xs mono text-[var(--red)]">
            ERROR: {tradeError}
          </div>
          <button
            onClick={() => setTradeError(null)}
            className="mt-1 text-[9px] text-[var(--green-dark)] hover:text-[var(--green)] uppercase tracking-wider"
          >
            [dismiss]
          </button>
        </div>
      )}

      {tradeSuccess && (
        <div className="border border-[rgba(0,255,65,0.2)] bg-[rgba(0,255,65,0.04)] p-3 mb-4">
          <div className="text-xs mono text-[var(--green)]">
            {tradeSuccess}
          </div>
          <button
            onClick={() => setTradeSuccess(null)}
            className="mt-1 text-[9px] text-[var(--green-dark)] hover:text-[var(--green)] uppercase tracking-wider"
          >
            [dismiss]
          </button>
        </div>
      )}

      {/* BUY / SELL button */}
      <button
        onClick={handleTrade}
        disabled={!canTrade || tradeMutation.isPending}
        className={`w-full border mono text-sm py-3 px-4 rounded-none font-bold uppercase tracking-wider transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
          side === "BUY"
            ? "border-[var(--green)] text-[var(--green)] hover:bg-[var(--green)] hover:text-black"
            : "border-[var(--red)] text-[var(--red)] hover:bg-[var(--red)] hover:text-black"
        }`}
      >
        {tradeMutation.isPending ? (
          <>
            SUBMITTING<span className="blink">_</span>
          </>
        ) : (
          `[ ${side} ${(market.outcomes?.[outcomeIdx] ?? "").toUpperCase()} — ${amount > 0 ? `$${amount.toFixed(2)}` : "$0.00"} ]`
        )}
      </button>
    </div>
  );
}

/* ================================================================== */
/*  Recent Trades Table                                                */
/* ================================================================== */

function RecentTradesTable({ trades }: { trades: RecentTrade[] }) {
  const statusColor = (status: string) => {
    switch (status) {
      case "submitted":
      case "executed":
        return "text-[var(--green)]";
      case "pending":
        return "text-[var(--amber)]";
      default:
        return "text-[var(--red)]";
    }
  };

  return (
    <div className="glass rounded-none p-5 slide-up">
      <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
        // RECENT MANUAL TRADES ({trades.length})
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs mono">
          <thead>
            <tr className="text-[10px] text-[var(--green-dark)] uppercase tracking-wider">
              <th className="text-left pb-2 pr-3">TIME</th>
              <th className="text-left pb-2 pr-3">MARKET</th>
              <th className="text-left pb-2 pr-3">SIDE</th>
              <th className="text-right pb-2 pr-3">AMT</th>
              <th className="text-left pb-2">STATUS</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t) => (
              <tr
                key={t.id}
                className="border-t border-[rgba(0,255,65,0.08)] hover:bg-[rgba(0,255,65,0.05)]"
              >
                <td className="py-2 pr-3 text-[var(--green-dim)]">
                  {t.timestamp?.slice(11, 19)}
                </td>
                <td className="py-2 pr-3 text-[var(--green)]">
                  {truncate(t.market, 35)}
                </td>
                <td className="py-2 pr-3">
                  <span
                    className={
                      t.side.includes("BUY")
                        ? "text-[var(--green)]"
                        : "text-[var(--red)]"
                    }
                  >
                    {t.side}
                  </span>
                </td>
                <td className="py-2 pr-3 text-right text-[var(--cyan)]">
                  ${t.amount.toFixed(2)}
                </td>
                <td className={`py-2 ${statusColor(t.status)}`}>
                  {t.status}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

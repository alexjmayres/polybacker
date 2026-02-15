"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiJson, apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";

interface Allocation {
  trader_address: string;
  weight: number;
  active: number;
}

interface Fund {
  id: number;
  owner_address: string;
  name: string;
  description: string;
  created_at: string;
  active: number;
  total_aum: number;
  nav_per_share: number;
  total_shares: number;
  allocations?: Allocation[];
}

interface FundTrade {
  id: number;
  fund_id: number;
  trader_address: string;
  amount: number;
  timestamp: string;
  token_id: string;
  side: string;
  market: string;
  status: string;
}

function FundCard({
  fund,
  isFeatured,
}: {
  fund: Fund;
  isFeatured: boolean;
}) {
  const [expanded, setExpanded] = useState(isFeatured);
  const [investAmount, setInvestAmount] = useState("");
  const [activeSection, setActiveSection] = useState<
    "info" | "trades"
  >("info");
  const queryClient = useQueryClient();
  const { isOwner } = useAuth();

  const { data: expandedFund } = useQuery<Fund>({
    queryKey: ["fund-detail", fund.id],
    queryFn: () => apiJson(`/api/funds/${fund.id}`),
    enabled: expanded,
    refetchInterval: 15000,
  });

  const { data: fundTrades = [] } = useQuery<FundTrade[]>({
    queryKey: ["fund-trades", fund.id],
    queryFn: () => apiJson(`/api/funds/${fund.id}/trades?limit=20`),
    enabled: expanded && activeSection === "trades",
    refetchInterval: 15000,
  });

  const investMutation = useMutation({
    mutationFn: async ({
      fundId,
      amount,
    }: {
      fundId: number;
      amount: number;
    }) => {
      const res = await apiFetch(`/api/funds/${fundId}/invest`, {
        method: "POST",
        body: JSON.stringify({ amount }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["funds"] });
      queryClient.invalidateQueries({ queryKey: ["my-investments"] });
      queryClient.invalidateQueries({ queryKey: ["fund-detail", fund.id] });
      setInvestAmount("");
    },
  });

  const truncate = (addr: string) =>
    `${addr.slice(0, 8)}...${addr.slice(-6)}`;

  const timeAgo = (ts: string) => {
    const diff = Date.now() - new Date(ts + "Z").getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    return `${Math.floor(hrs / 24)}d`;
  };

  const navChange = fund.nav_per_share - 1.0;
  const navChangePct = (navChange * 100).toFixed(2);
  const isPositive = navChange >= 0;

  return (
    <div className="slide-up">
      {/* Fund header */}
      <div
        className={`flex items-center justify-between px-3 py-3 cursor-pointer transition-colors ${
          isFeatured
            ? "bg-[rgba(0,255,65,0.05)] border-2 border-[var(--green)]"
            : "bg-[rgba(0,255,65,0.02)] border border-[rgba(0,255,65,0.08)]"
        }`}
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {isFeatured && (
              <span className="text-[8px] text-black bg-[var(--green)] px-1.5 py-0.5 font-bold tracking-wider">
                FLAGSHIP
              </span>
            )}
            <span className="text-[var(--green)] font-bold text-sm uppercase">
              {fund.name}
            </span>
            <span
              className={`mono text-[10px] ${
                isPositive ? "text-[var(--green)]" : "text-[var(--red)]"
              }`}
            >
              {isPositive ? "+" : ""}
              {navChangePct}%
            </span>
          </div>
          <div className="flex items-center gap-3 text-[10px] text-[var(--green-dark)] mono mt-0.5">
            <span>
              AUM: ${fund.total_aum.toFixed(2)}
            </span>
            <span>
              NAV: ${fund.nav_per_share.toFixed(4)}
            </span>
            <span>
              {fund.total_shares.toFixed(2)} shares
            </span>
          </div>
        </div>
        <span className="text-[10px] text-[var(--green-dark)]">
          {expanded ? "[-]" : "[+]"}
        </span>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div
          className={`border-t-0 bg-[rgba(0,0,0,0.2)] px-3 py-3 space-y-3 slide-up ${
            isFeatured
              ? "border-2 border-t-0 border-[var(--green)]"
              : "border border-t-0 border-[rgba(0,255,65,0.08)]"
          }`}
        >
          {/* Description */}
          {fund.description && (
            <p className="mono text-xs text-[var(--green-dim)]">
              {fund.description}
            </p>
          )}

          {/* Section tabs */}
          <div className="flex gap-2">
            <button
              onClick={() => setActiveSection("info")}
              className={`text-[10px] font-bold px-2 py-1 transition-colors ${
                activeSection === "info"
                  ? "text-[var(--green)] border border-[var(--green)]"
                  : "text-[var(--green-dark)] border border-[var(--panel-border)]"
              }`}
            >
              ALLOCATIONS
            </button>
            <button
              onClick={() => setActiveSection("trades")}
              className={`text-[10px] font-bold px-2 py-1 transition-colors ${
                activeSection === "trades"
                  ? "text-[var(--cyan)] border border-[var(--cyan)]"
                  : "text-[var(--green-dark)] border border-[var(--panel-border)]"
              }`}
            >
              RECENT TRADES
            </button>
          </div>

          {/* Allocations section */}
          {activeSection === "info" &&
            expandedFund?.allocations &&
            expandedFund.allocations.length > 0 && (
              <div>
                <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
                  TRADER ALLOCATIONS
                </div>
                <div className="space-y-1">
                  {expandedFund.allocations.map((alloc) => (
                    <div
                      key={alloc.trader_address}
                      className="flex items-center justify-between"
                    >
                      <span className="mono text-xs text-[var(--cyan)]">
                        {truncate(alloc.trader_address)}
                      </span>
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1 bg-[var(--panel-border)] overflow-hidden">
                          <div
                            className="h-full bg-[var(--green)]"
                            style={{
                              width: `${alloc.weight * 100}%`,
                            }}
                          />
                        </div>
                        <span className="mono text-xs text-[var(--green-dim)]">
                          {(alloc.weight * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

          {activeSection === "info" &&
            expandedFund?.allocations?.length === 0 && (
              <p className="mono text-xs text-[var(--green-dark)] text-center py-2">
                no traders allocated yet
              </p>
            )}

          {/* Trades section */}
          {activeSection === "trades" && (
            <div className="space-y-1 max-h-[200px] overflow-y-auto">
              {fundTrades.length === 0 ? (
                <p className="mono text-xs text-[var(--green-dark)] text-center py-2">
                  no fund trades yet
                </p>
              ) : (
                fundTrades.map((trade) => (
                  <div
                    key={trade.id}
                    className="flex items-center justify-between bg-[rgba(0,255,65,0.02)] border border-[rgba(0,255,65,0.05)] px-2 py-1"
                  >
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <span
                        className={`text-[9px] font-bold px-1 ${
                          trade.side === "BUY"
                            ? "text-[var(--green)]"
                            : "text-[var(--red)]"
                        }`}
                      >
                        {trade.side}
                      </span>
                      <span className="mono text-[10px] text-[var(--green)] truncate">
                        {trade.market || "Unknown"}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="mono text-[10px] text-[var(--cyan)]">
                        ${trade.amount.toFixed(2)}
                      </span>
                      <span className="mono text-[9px] text-[var(--green-dark)]">
                        {timeAgo(trade.timestamp)}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Invest form — available to everyone */}
          <div className="pt-2 border-t border-[var(--panel-border)]">
            <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
              {isOwner ? "INVEST IN FUND" : "INVEST"}
            </div>
            <div className="flex gap-2">
              <input
                type="number"
                placeholder="$ Amount"
                value={investAmount}
                onChange={(e) => setInvestAmount(e.target.value)}
                onKeyDown={(e) => {
                  if (
                    e.key === "Enter" &&
                    investAmount &&
                    parseFloat(investAmount) > 0
                  )
                    investMutation.mutate({
                      fundId: fund.id,
                      amount: parseFloat(investAmount),
                    });
                }}
                className="flex-1 bg-transparent border border-[var(--panel-border)] rounded-none px-3 py-2 text-xs mono text-[var(--green)] focus:outline-none focus:border-[var(--green)]"
              />
              <button
                onClick={() =>
                  investMutation.mutate({
                    fundId: fund.id,
                    amount: parseFloat(investAmount),
                  })
                }
                disabled={
                  !investAmount ||
                  parseFloat(investAmount) <= 0 ||
                  investMutation.isPending
                }
                className="border border-[var(--cyan)] text-[var(--cyan)] hover:bg-[var(--cyan)] hover:text-black disabled:opacity-30 px-4 py-2 rounded-none text-xs font-bold transition-colors"
              >
                {investMutation.isPending ? "..." : "[INVEST]"}
              </button>
            </div>
            {investMutation.isError && (
              <p className="text-xs text-[var(--red)] mt-1 mono">
                ERR: {investMutation.error?.message}
              </p>
            )}
            {investMutation.isSuccess && (
              <p className="text-xs text-[var(--green)] mt-1 mono">
                Investment successful
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function FundList() {
  const { data: funds = [], isLoading } = useQuery<Fund[]>({
    queryKey: ["funds"],
    queryFn: () => apiJson("/api/funds"),
    refetchInterval: 15000,
    retry: false,
  });

  // Sort: PB500 Master Fund always first
  const sorted = [...funds].sort((a, b) => {
    if (a.name === "PB500 Master Fund") return -1;
    if (b.name === "PB500 Master Fund") return 1;
    return 0;
  });

  return (
    <div className="glass rounded-none p-4 sm:p-5">
      <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
        // AVAILABLE FUNDS
      </h3>

      {isLoading ? (
        <div className="text-center py-8">
          <span className="mono text-sm text-[var(--green-dim)]">
            LOADING FUNDS<span className="blink">_</span>
          </span>
        </div>
      ) : sorted.length === 0 ? (
        <div className="text-center py-8">
          <span className="mono text-sm text-[var(--green-dark)]">
            no funds available
          </span>
        </div>
      ) : (
        <div className="space-y-2">
          {sorted.map((fund) => (
            <FundCard
              key={fund.id}
              fund={fund}
              isFeatured={fund.name === "PB500 Master Fund"}
            />
          ))}
        </div>
      )}
    </div>
  );
}

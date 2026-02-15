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

export function FundList() {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [investAmount, setInvestAmount] = useState("");
  const queryClient = useQueryClient();
  const { isOwner } = useAuth();

  const { data: funds = [], isLoading } = useQuery<Fund[]>({
    queryKey: ["funds"],
    queryFn: () => apiJson("/api/funds"),
    refetchInterval: 15000,
    retry: false,
  });

  const { data: expandedFund } = useQuery<Fund>({
    queryKey: ["fund-detail", expandedId],
    queryFn: () => apiJson(`/api/funds/${expandedId}`),
    enabled: expandedId !== null,
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
      setInvestAmount("");
    },
  });

  const truncate = (addr: string) =>
    `${addr.slice(0, 8)}...${addr.slice(-6)}`;

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
      ) : funds.length === 0 ? (
        <div className="text-center py-8">
          <span className="mono text-sm text-[var(--green-dark)]">
            no funds available
          </span>
        </div>
      ) : (
        <div className="space-y-2">
          {funds.map((fund) => (
            <div key={fund.id} className="slide-up">
              {/* Fund header */}
              <div
                className="flex items-center justify-between bg-[rgba(0,255,65,0.02)] border border-[rgba(0,255,65,0.08)] px-3 py-2 cursor-pointer"
                onClick={() =>
                  setExpandedId(expandedId === fund.id ? null : fund.id)
                }
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[var(--green)] font-bold text-sm uppercase">
                      {fund.name}
                    </span>
                    <span className="text-[10px] text-[var(--green-dim)]">
                      NAV: ${fund.nav_per_share.toFixed(4)}
                    </span>
                  </div>
                  <div className="text-[10px] text-[var(--green-dark)] mono">
                    AUM: ${fund.total_aum.toFixed(2)} // {fund.total_shares.toFixed(2)} shares
                  </div>
                </div>
                <span className="text-[10px] text-[var(--green-dark)]">
                  {expandedId === fund.id ? "[-]" : "[+]"}
                </span>
              </div>

              {/* Expanded details */}
              {expandedId === fund.id && (
                <div className="border border-t-0 border-[rgba(0,255,65,0.08)] bg-[rgba(0,0,0,0.2)] px-3 py-3 space-y-3 slide-up">
                  {fund.description && (
                    <p className="mono text-xs text-[var(--green-dim)]">
                      {fund.description}
                    </p>
                  )}

                  {/* Allocations */}
                  {expandedFund?.allocations &&
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

                  {/* Invest form (non-owner) */}
                  {!isOwner && (
                    <div className="pt-2 border-t border-[var(--panel-border)]">
                      <div className="flex gap-2">
                        <input
                          type="number"
                          placeholder="$ Amount"
                          value={investAmount}
                          onChange={(e) => setInvestAmount(e.target.value)}
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
                          [INVEST]
                        </button>
                      </div>
                      {investMutation.isError && (
                        <p className="text-xs text-[var(--red)] mt-1 mono">
                          ERR: {investMutation.error?.message}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

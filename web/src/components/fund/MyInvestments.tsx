"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiJson, apiFetch } from "@/lib/api";

interface Investment {
  id: number;
  fund_id: number;
  fund_name: string;
  amount_invested: number;
  shares: number;
  invested_at: string;
  status: string;
  nav_per_share: number;
  fund_active: number;
}

export function MyInvestments() {
  const queryClient = useQueryClient();

  const { data: investments = [] } = useQuery<Investment[]>({
    queryKey: ["my-investments"],
    queryFn: () => apiJson("/api/funds/my-investments"),
    refetchInterval: 15000,
    retry: false,
  });

  const withdrawMutation = useMutation({
    mutationFn: async (investmentId: number) => {
      const res = await apiFetch(
        `/api/funds/investments/${investmentId}/withdraw`,
        { method: "POST" }
      );
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-investments"] });
      queryClient.invalidateQueries({ queryKey: ["funds"] });
    },
  });

  const activeInvestments = investments.filter((i) => i.status === "active");

  return (
    <div className="glass rounded-none p-5">
      <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
        // MY INVESTMENTS
      </h3>

      {activeInvestments.length === 0 ? (
        <p className="mono text-sm text-[var(--green-dark)] text-center py-4">
          no active investments
        </p>
      ) : (
        <div className="space-y-2">
          {activeInvestments.map((inv) => {
            const currentValue = inv.shares * inv.nav_per_share;
            const pnl = currentValue - inv.amount_invested;
            const pnlPct =
              inv.amount_invested > 0
                ? ((pnl / inv.amount_invested) * 100).toFixed(1)
                : "0.0";

            return (
              <div
                key={inv.id}
                className="bg-[rgba(0,255,65,0.02)] border border-[rgba(0,255,65,0.08)] px-3 py-2"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[var(--green)] font-bold text-xs uppercase">
                    {inv.fund_name}
                  </span>
                  <button
                    onClick={() => withdrawMutation.mutate(inv.id)}
                    disabled={withdrawMutation.isPending}
                    className="text-[10px] text-[var(--red)] hover:text-[var(--red)] border border-[var(--red)] px-2 py-0.5 opacity-60 hover:opacity-100 transition-opacity"
                  >
                    [WITHDRAW]
                  </button>
                </div>
                <div className="flex items-center justify-between text-[10px] mono">
                  <span className="text-[var(--green-dark)]">
                    Invested: ${inv.amount_invested.toFixed(2)}
                  </span>
                  <span className="text-[var(--cyan)]">
                    Value: ${currentValue.toFixed(2)}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[10px] mono">
                  <span className="text-[var(--green-dark)]">
                    {inv.shares.toFixed(4)} shares
                  </span>
                  <span
                    className={
                      pnl >= 0
                        ? "text-[var(--green)]"
                        : "text-[var(--red)]"
                    }
                  >
                    {pnl >= 0 ? "+" : ""}${pnl.toFixed(2)} ({pnlPct}%)
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

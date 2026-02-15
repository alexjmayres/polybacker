"use client";

import { useQuery } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";

interface Trade {
  id: number;
  timestamp: string;
  market: string;
  side: string;
  amount: number;
  copied_from: string;
  status: string;
}

export function CopyTradesList() {
  const { data: trades = [] } = useQuery<Trade[]>({
    queryKey: ["copy-trades"],
    queryFn: () => apiJson("/api/copy/trades?limit=20"),
    refetchInterval: 10000,
  });

  const statusColor = (status: string) => {
    switch (status) {
      case "executed":
        return "text-[var(--green)]";
      case "dry_run":
        return "text-[var(--amber)]";
      default:
        return "text-[var(--red)]";
    }
  };

  const truncate = (s: string | null, len: number) =>
    s ? (s.length > len ? s.slice(0, len) + "..." : s) : "--";

  return (
    <div className="glass rounded-none p-5">
      <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
        // RECENT TRADES
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs mono">
          <thead>
            <tr className="text-[10px] text-[var(--green-dark)] uppercase tracking-wider">
              <th className="text-left pb-2 pr-3">TIME</th>
              <th className="text-left pb-2 pr-3">MARKET</th>
              <th className="text-left pb-2 pr-3">SIDE</th>
              <th className="text-right pb-2 pr-3">AMT</th>
              <th className="text-left pb-2 pr-3">FROM</th>
              <th className="text-left pb-2">STATUS</th>
            </tr>
          </thead>
          <tbody>
            {trades.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-center text-[var(--green-dark)] py-8 mono">
                  -- no copy trades --
                </td>
              </tr>
            ) : (
              trades.map((t) => (
                <tr
                  key={t.id}
                  className="border-t border-[rgba(0,255,65,0.08)] hover:bg-[rgba(0,255,65,0.05)]"
                >
                  <td className="py-2 pr-3 text-[var(--green-dim)]">
                    {t.timestamp?.slice(11, 19)}
                  </td>
                  <td className="py-2 pr-3 text-[var(--green)]">
                    {truncate(t.market, 30)}
                  </td>
                  <td className="py-2 pr-3">
                    <span className={t.side === "BUY" ? "text-[var(--green)]" : "text-[var(--red)]"}>
                      {t.side}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-right text-[var(--cyan)]">
                    ${t.amount.toFixed(2)}
                  </td>
                  <td className="py-2 pr-3 text-[var(--magenta)]">
                    {truncate(t.copied_from, 10)}
                  </td>
                  <td className={`py-2 ${statusColor(t.status)}`}>
                    {t.status}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

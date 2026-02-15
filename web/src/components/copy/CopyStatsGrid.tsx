"use client";

import { useQuery } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";

interface CopyStats {
  total_trades: number;
  total_spent: number;
  failed_trades: number;
  daily_spend: number;
  daily_limit: number;
}

export function CopyStatsGrid() {
  const { data: stats } = useQuery<CopyStats>({
    queryKey: ["copy-stats"],
    queryFn: () => apiJson("/api/copy/stats"),
    refetchInterval: 10000,
  });

  const items = [
    {
      label: "TRADES",
      value: String(stats?.total_trades ?? 0),
      color: "text-[var(--green)]",
    },
    {
      label: "INVESTED",
      value: `$${(stats?.total_spent ?? 0).toFixed(2)}`,
      color: "text-[var(--cyan)]",
    },
    {
      label: "TODAY",
      value: `$${(stats?.daily_spend ?? 0).toFixed(2)}/$${(stats?.daily_limit ?? 0).toFixed(0)}`,
      color: "text-[var(--amber)]",
    },
    {
      label: "FAILED",
      value: String(stats?.failed_trades ?? 0),
      color: "text-[var(--red)]",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {items.map((item) => (
        <div key={item.label} className="glass rounded-none p-4 slide-up">
          <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
            {item.label}
          </div>
          <div className={`text-2xl font-bold mono ${item.color}`}>
            {item.value}
          </div>
        </div>
      ))}
    </div>
  );
}

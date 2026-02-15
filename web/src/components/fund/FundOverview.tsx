"use client";

import { useQuery } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";

interface Fund {
  id: number;
  name: string;
  total_aum: number;
  nav_per_share: number;
  active: number;
}

export function FundOverview() {
  const { data: funds = [] } = useQuery<Fund[]>({
    queryKey: ["funds"],
    queryFn: () => apiJson("/api/funds"),
    refetchInterval: 15000,
    retry: false,
  });

  const totalAum = funds.reduce((s, f) => s + f.total_aum, 0);
  const avgNav =
    funds.length > 0
      ? funds.reduce((s, f) => s + f.nav_per_share, 0) / funds.length
      : 1.0;

  const items = [
    {
      label: "ACTIVE FUNDS",
      value: String(funds.length),
      color: "text-[var(--green)]",
    },
    {
      label: "TOTAL AUM",
      value: `$${totalAum.toFixed(2)}`,
      color: "text-[var(--cyan)]",
    },
    {
      label: "AVG NAV",
      value: `$${avgNav.toFixed(4)}`,
      color: "text-[var(--amber)]",
    },
  ];

  return (
    <div className="grid grid-cols-3 gap-3">
      {items.map((item) => (
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
  );
}

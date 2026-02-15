"use client";

import { ArbStatsGrid } from "./ArbStatsGrid";
import { ArbControls } from "./ArbControls";
import { ArbTradesList } from "./ArbTradesList";
import { PnlChart } from "@/components/PnlChart";

export function ArbPanel() {
  return (
    <div className="space-y-6 slide-up">
      <ArbStatsGrid />
      <PnlChart strategy="arb" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <ArbControls />
        </div>
        <div className="lg:col-span-2">
          <ArbTradesList />
        </div>
      </div>
    </div>
  );
}

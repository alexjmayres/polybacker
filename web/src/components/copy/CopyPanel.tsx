"use client";

import { CopyStatsGrid } from "./CopyStatsGrid";
import { FollowedTraders } from "./FollowedTraders";
import { CopyTradesList } from "./CopyTradesList";
import { CopyControls } from "./CopyControls";
import { PnlChart } from "@/components/PnlChart";

export function CopyPanel() {
  return (
    <div className="space-y-6 slide-up">
      <CopyStatsGrid />
      <PnlChart strategy="copy" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-6">
          <CopyControls />
          <FollowedTraders />
        </div>
        <div className="lg:col-span-2">
          <CopyTradesList />
        </div>
      </div>
    </div>
  );
}

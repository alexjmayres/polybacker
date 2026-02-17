"use client";

import { CopyStatsGrid } from "./CopyStatsGrid";
import { FollowedTraders } from "./FollowedTraders";
import { CopyTradesList } from "./CopyTradesList";
import { CopyControls } from "./CopyControls";
import { TraderPnlTable } from "./TraderPnlTable";

export function CopyPanel() {
  return (
    <div className="space-y-6 slide-up">
      <CopyStatsGrid />
      {/* Follow UI at the top with controls */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <FollowedTraders />
        <CopyControls />
      </div>
      {/* PNL per trader since followed */}
      <TraderPnlTable />
      {/* Trade history */}
      <CopyTradesList />
    </div>
  );
}

"use client";

import { FundOverview } from "./FundOverview";
import { FundList } from "./FundList";
import { MyInvestments } from "./MyInvestments";
import { FundControls } from "./FundControls";

export function FundPanel() {
  return (
    <div className="space-y-6 slide-up">
      <FundOverview />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <FundList />
        </div>
        <div className="lg:col-span-1 space-y-6">
          <MyInvestments />
          <FundControls />
        </div>
      </div>
    </div>
  );
}

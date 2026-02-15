"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";

interface Position {
  asset: string;
  market?: string;
  title?: string;
  outcome?: string;
  size: number | string;
  avgPrice?: number | string;
  currentPrice?: number | string;
  pnl?: number | string;
  realizedPnl?: number | string;
  curPrice?: number | string;
}

interface Trade {
  timestamp?: string;
  created_at?: string;
  time?: string;
  side: string;
  size: number | string;
  price: number | string;
  asset_id?: string;
  market?: string;
  title?: string;
}

interface TraderProfileData {
  positions: Position[];
  trades: Trade[];
}

/* ─── Mini PnL chart from raw trade data ─── */

interface PnlPoint {
  date: string;
  trades: number;
  volume: number;
  pnl: number;
  cumulative: number;
}

function buildPnlFromTrades(trades: Trade[], days: number): PnlPoint[] {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - days);
  const cutoffStr = cutoff.toISOString().slice(0, 10);

  // Group trades by date
  const byDate: Record<string, { count: number; volume: number; pnl: number }> = {};

  for (const t of trades) {
    const ts = t.timestamp || t.created_at || t.time || "";
    const dateStr = typeof ts === "string" ? ts.slice(0, 10) : new Date(Number(ts) * 1000).toISOString().slice(0, 10);
    if (dateStr < cutoffStr) continue;

    if (!byDate[dateStr]) {
      byDate[dateStr] = { count: 0, volume: 0, pnl: 0 };
    }
    const size = parseFloat(String(t.size || 0));
    const price = parseFloat(String(t.price || 0));
    const usd = size * price;

    byDate[dateStr].count += 1;
    byDate[dateStr].volume += usd;
    // Rough PnL estimate: buying below 0.5 = potential upside, selling above 0.5 = profit take
    const side = (t.side || "").toUpperCase();
    if (side === "SELL" && price > 0.5) {
      byDate[dateStr].pnl += usd * (price - 0.5) * 0.5;
    } else if (side === "BUY" && price < 0.5) {
      byDate[dateStr].pnl += usd * (0.5 - price) * 0.3;
    }
  }

  const dates = Object.keys(byDate).sort();
  const points: PnlPoint[] = [];
  let cumulative = 0;
  for (const date of dates) {
    const d = byDate[date];
    cumulative += d.pnl;
    points.push({
      date,
      trades: d.count,
      volume: Math.round(d.volume * 100) / 100,
      pnl: Math.round(d.pnl * 100) / 100,
      cumulative: Math.round(cumulative * 100) / 100,
    });
  }
  return points;
}

/* ─── Minimal chart SVG ─── */

function MiniChart({ data, label }: { data: PnlPoint[]; label: string }) {
  if (data.length < 2) {
    return (
      <div className="h-20 flex items-center justify-center">
        <span className="mono text-[10px] text-[var(--green-dark)]">
          NOT ENOUGH DATA
        </span>
      </div>
    );
  }

  const W = 300;
  const H = 80;
  const PAD = 5;
  const chartW = W - PAD * 2;
  const chartH = H - PAD * 2;

  const values = data.map((d) => d.cumulative);
  const maxVal = Math.max(...values, 1);
  const minVal = Math.min(...values, 0);
  const range = maxVal - minVal || 1;

  const toX = (i: number) => PAD + (i / (data.length - 1)) * chartW;
  const toY = (v: number) => PAD + chartH - ((v - minVal) / range) * chartH;

  const linePath = data
    .map((d, i) => `${i === 0 ? "M" : "L"} ${toX(i).toFixed(1)} ${toY(d.cumulative).toFixed(1)}`)
    .join(" ");

  const last = data[data.length - 1];
  const isPositive = last.cumulative >= 0;
  const color = isPositive ? "var(--green)" : "var(--red)";

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[9px] text-[var(--green-dark)] uppercase">{label}</span>
        <span className={`mono text-[10px] ${isPositive ? "text-[var(--green)]" : "text-[var(--red)]"}`}>
          {isPositive ? "+" : ""}${last.cumulative.toFixed(2)}
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
        {/* Zero line */}
        {minVal < 0 && maxVal > 0 && (
          <line
            x1={PAD} y1={toY(0)} x2={W - PAD} y2={toY(0)}
            stroke="rgba(0,255,65,0.15)" strokeWidth="0.5"
          />
        )}
        <path d={linePath} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
        <circle cx={toX(data.length - 1)} cy={toY(last.cumulative)} r="2.5" fill={color} />
      </svg>
    </div>
  );
}

/* ─── Main TraderProfile component ─── */

export function TraderProfile({ address }: { address: string }) {
  const [chartDays, setChartDays] = useState<30 | 90>(30);

  const { data, isLoading, isError } = useQuery<TraderProfileData>({
    queryKey: ["trader-profile", address],
    queryFn: () => apiJson(`/api/copy/traders/${address}/profile`),
    refetchInterval: 30000,
    staleTime: 15000,
  });

  if (isLoading) {
    return (
      <div className="py-4 text-center">
        <span className="mono text-[10px] text-[var(--green-dim)]">
          LOADING TRADER DATA<span className="blink">_</span>
        </span>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="py-3 text-center">
        <span className="mono text-[10px] text-[var(--red)]">
          COULD NOT LOAD TRADER DATA
        </span>
      </div>
    );
  }

  const { positions, trades } = data;
  const pnl30 = buildPnlFromTrades(trades, 30);
  const pnl90 = buildPnlFromTrades(trades, 90);
  const totalTrades30 = pnl30.reduce((s, d) => s + d.trades, 0);
  const totalVolume30 = pnl30.reduce((s, d) => s + d.volume, 0);

  return (
    <div className="space-y-3">
      {/* Trade Stats */}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="text-[9px] text-[var(--green-dark)] uppercase">POSITIONS</div>
          <div className="mono text-sm text-[var(--cyan)]">{positions.length}</div>
        </div>
        <div>
          <div className="text-[9px] text-[var(--green-dark)] uppercase">30D TRADES</div>
          <div className="mono text-sm text-[var(--green)]">{totalTrades30}</div>
        </div>
        <div>
          <div className="text-[9px] text-[var(--green-dark)] uppercase">30D VOLUME</div>
          <div className="mono text-sm text-[var(--amber)]">
            ${totalVolume30 >= 1000 ? `${(totalVolume30/1000).toFixed(1)}k` : totalVolume30.toFixed(0)}
          </div>
        </div>
      </div>

      {/* PnL Charts */}
      <div className="border border-[rgba(0,255,65,0.08)] bg-[rgba(0,0,0,0.2)] p-2 space-y-2">
        <MiniChart data={pnl30} label="30 DAY PNL" />
        <MiniChart data={pnl90} label="90 DAY PNL" />
      </div>

      {/* Open Positions */}
      {positions.length > 0 && (
        <div>
          <div className="text-[9px] text-[var(--green-dark)] uppercase tracking-widest mb-1">
            CURRENT POSITIONS
          </div>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {positions.slice(0, 10).map((pos, i) => {
              const size = parseFloat(String(pos.size || 0));
              const title = pos.title || pos.market || pos.asset || "Unknown";
              const outcome = pos.outcome || "";
              return (
                <div
                  key={i}
                  className="flex items-center justify-between text-[10px] mono px-1 py-0.5"
                >
                  <span className="text-[var(--green-dim)] truncate max-w-[60%]">
                    {title.length > 40 ? title.slice(0, 40) + "..." : title}
                    {outcome && <span className="text-[var(--cyan)]"> ({outcome})</span>}
                  </span>
                  <span className="text-[var(--green)] shrink-0 ml-2">
                    {size >= 1000 ? `${(size/1000).toFixed(1)}k` : size.toFixed(1)} shares
                  </span>
                </div>
              );
            })}
            {positions.length > 10 && (
              <div className="text-[9px] text-[var(--green-dark)] text-center">
                +{positions.length - 10} more
              </div>
            )}
          </div>
        </div>
      )}

      {positions.length === 0 && (
        <div className="text-center py-2">
          <span className="mono text-[10px] text-[var(--green-dark)]">
            NO OPEN POSITIONS
          </span>
        </div>
      )}
    </div>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";

interface PnlPoint {
  date: string;
  trades: number;
  spent: number;
  profit: number;
  cumulative_profit: number;
}

interface PnlChartProps {
  strategy: "copy" | "arb";
}

/* ─── Demo data shown when no real trades exist ─── */
function generateDemoData(): PnlPoint[] {
  const points: PnlPoint[] = [];
  const now = new Date();
  let cumulative = 0;

  for (let i = 29; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().slice(0, 10);

    const trades = Math.floor(Math.random() * 8) + 1;
    const spent = Math.round((Math.random() * 50 + 10) * 100) / 100;
    const profit =
      Math.round((Math.random() * 20 - 5) * 100) / 100; // -5 to +15
    cumulative = Math.round((cumulative + profit) * 100) / 100;

    points.push({
      date: dateStr,
      trades,
      spent,
      profit,
      cumulative_profit: cumulative,
    });
  }
  return points;
}

/* ─── Retro SVG chart renderer ─── */

function RetroChart({ data, isDemo }: { data: PnlPoint[]; isDemo: boolean }) {
  if (data.length === 0) return null;

  const W = 600;
  const H = 200;
  const PAD_L = 55;
  const PAD_R = 10;
  const PAD_T = 15;
  const PAD_B = 30;
  const chartW = W - PAD_L - PAD_R;
  const chartH = H - PAD_T - PAD_B;

  const values = data.map((d) => d.cumulative_profit);
  const maxVal = Math.max(...values, 1);
  const minVal = Math.min(...values, 0);
  const range = maxVal - minVal || 1;

  const toX = (i: number) => PAD_L + (i / (data.length - 1 || 1)) * chartW;
  const toY = (v: number) =>
    PAD_T + chartH - ((v - minVal) / range) * chartH;

  /* main line path */
  const linePath = data
    .map((d, i) => `${i === 0 ? "M" : "L"} ${toX(i).toFixed(1)} ${toY(d.cumulative_profit).toFixed(1)}`)
    .join(" ");

  /* area fill under the line */
  const areaPath = `${linePath} L ${toX(data.length - 1).toFixed(1)} ${(PAD_T + chartH).toFixed(1)} L ${PAD_L.toFixed(1)} ${(PAD_T + chartH).toFixed(1)} Z`;

  /* zero line Y */
  const zeroY = toY(0);

  /* grid lines — 5 horizontal */
  const gridLines = [];
  const steps = 4;
  for (let i = 0; i <= steps; i++) {
    const val = minVal + (range / steps) * i;
    const y = toY(val);
    gridLines.push({ y, label: val >= 0 ? `+$${val.toFixed(0)}` : `-$${Math.abs(val).toFixed(0)}` });
  }

  /* x-axis labels — show every ~7th date */
  const xLabels: { x: number; label: string }[] = [];
  const step = Math.max(1, Math.floor(data.length / 5));
  for (let i = 0; i < data.length; i += step) {
    xLabels.push({
      x: toX(i),
      label: data[i].date.slice(5), // MM-DD
    });
  }

  /* final value */
  const lastPoint = data[data.length - 1];
  const isPositive = lastPoint.cumulative_profit >= 0;
  const lineColor = isPositive ? "var(--green)" : "var(--red)";
  const glowColor = isPositive
    ? "rgba(0,255,65,0.6)"
    : "rgba(255,51,51,0.6)";

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full h-auto"
      style={{ filter: "drop-shadow(0 0 2px rgba(0,255,65,0.2))" }}
    >
      <defs>
        <linearGradient id={`areaFill-${isPositive}`} x1="0" y1="0" x2="0" y2="1">
          <stop
            offset="0%"
            stopColor={isPositive ? "rgba(0,255,65,0.15)" : "rgba(255,51,51,0.15)"}
          />
          <stop
            offset="100%"
            stopColor="rgba(0,0,0,0)"
          />
        </linearGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Grid lines */}
      {gridLines.map((g, i) => (
        <g key={i}>
          <line
            x1={PAD_L}
            y1={g.y}
            x2={W - PAD_R}
            y2={g.y}
            stroke="rgba(0,255,65,0.08)"
            strokeWidth="0.5"
            strokeDasharray="4 4"
          />
          <text
            x={PAD_L - 5}
            y={g.y + 3}
            textAnchor="end"
            fill="var(--green-dark)"
            fontSize="9"
            fontFamily="VT323, monospace"
          >
            {g.label}
          </text>
        </g>
      ))}

      {/* Zero line */}
      {minVal < 0 && maxVal > 0 && (
        <line
          x1={PAD_L}
          y1={zeroY}
          x2={W - PAD_R}
          y2={zeroY}
          stroke="rgba(0,255,65,0.2)"
          strokeWidth="0.5"
        />
      )}

      {/* X-axis labels */}
      {xLabels.map((l, i) => (
        <text
          key={i}
          x={l.x}
          y={H - 5}
          textAnchor="middle"
          fill="var(--green-dark)"
          fontSize="9"
          fontFamily="VT323, monospace"
        >
          {l.label}
        </text>
      ))}

      {/* Area fill */}
      <path
        d={areaPath}
        fill={`url(#areaFill-${isPositive})`}
      />

      {/* Main line */}
      <path
        d={linePath}
        fill="none"
        stroke={lineColor}
        strokeWidth="1.5"
        strokeLinejoin="round"
        filter="url(#glow)"
      />

      {/* Data points */}
      {data.map((d, i) => (
        <circle
          key={i}
          cx={toX(i)}
          cy={toY(d.cumulative_profit)}
          r="2"
          fill={lineColor}
          opacity="0.7"
        >
          <title>
            {d.date}: {d.cumulative_profit >= 0 ? "+" : ""}${d.cumulative_profit.toFixed(2)} ({d.trades} trades)
          </title>
        </circle>
      ))}

      {/* Final value label */}
      <text
        x={toX(data.length - 1) + 2}
        y={toY(lastPoint.cumulative_profit) - 6}
        fill={lineColor}
        fontSize="11"
        fontFamily="VT323, monospace"
        filter="url(#glow)"
      >
        {isPositive ? "+" : ""}${lastPoint.cumulative_profit.toFixed(2)}
      </text>

      {/* Demo watermark */}
      {isDemo && (
        <text
          x={W / 2}
          y={H / 2}
          textAnchor="middle"
          fill="rgba(0,255,65,0.1)"
          fontSize="24"
          fontFamily="'Press Start 2P', cursive"
        >
          DEMO DATA
        </text>
      )}
    </svg>
  );
}

/* ─── Main PnL Chart Component ─── */

export function PnlChart({ strategy }: PnlChartProps) {
  const endpoint = strategy === "copy" ? "/api/copy/pnl" : "/api/arb/pnl";

  const { data, isLoading, isError } = useQuery<PnlPoint[]>({
    queryKey: [endpoint],
    queryFn: () => apiJson(endpoint + "?days=30"),
    refetchInterval: 30_000,
  });

  const hasRealData = data && data.length > 0;
  const chartData = hasRealData ? data : generateDemoData();
  const isDemo = !hasRealData;

  /* Summary stats from the series */
  const totalProfit = chartData.reduce((s, d) => s + d.profit, 0);
  const totalTrades = chartData.reduce((s, d) => s + d.trades, 0);
  const totalSpent = chartData.reduce((s, d) => s + d.spent, 0);
  const isPositive = totalProfit >= 0;

  return (
    <div className="glass rounded-none p-4 sm:p-5 slide-up">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <span className="text-[var(--green-dark)] text-xs">
            // PNL OVERVIEW
          </span>
          <div className="flex items-center gap-3 mt-1">
            <span
              className={`mono text-lg sm:text-xl font-bold ${
                isPositive ? "text-[var(--green)]" : "text-[var(--red)]"
              }`}
            >
              {isPositive ? "+" : ""}${totalProfit.toFixed(2)}
            </span>
            <span className="mono text-xs text-[var(--green-dim)] opacity-60">
              30D
            </span>
            {isDemo && (
              <span className="mono text-[10px] text-[var(--amber)] border border-[var(--amber)] px-2 py-0.5 opacity-60">
                SIMULATED
              </span>
            )}
          </div>
        </div>
        <div className="text-right mono text-xs text-[var(--green-dim)] space-y-0.5">
          <div>
            <span className="opacity-50">TRADES:</span>{" "}
            <span className="text-[var(--cyan)]">{totalTrades}</span>
          </div>
          <div>
            <span className="opacity-50">VOLUME:</span>{" "}
            <span className="text-[var(--amber)]">
              ${totalSpent.toFixed(0)}
            </span>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="border border-[var(--panel-border)] bg-[rgba(0,0,0,0.3)] p-2">
        {isLoading ? (
          <div className="h-[160px] flex items-center justify-center">
            <span className="mono text-sm text-[var(--green-dim)]">
              LOADING CHART DATA<span className="blink">_</span>
            </span>
          </div>
        ) : isError && !isDemo ? (
          <div className="h-[160px] flex items-center justify-center">
            <span className="mono text-sm text-[var(--red)]">
              ERROR FETCHING DATA
            </span>
          </div>
        ) : (
          <RetroChart data={chartData} isDemo={isDemo} />
        )}
      </div>

      {/* Bottom bar legend */}
      <div className="flex items-center gap-4 mt-3 mono text-[10px] text-[var(--green-dim)] opacity-50">
        <div className="flex items-center gap-1">
          <div
            className="w-3 h-[2px]"
            style={{ background: "var(--green)" }}
          />
          <span>CUMULATIVE P&L</span>
        </div>
        <div className="flex items-center gap-1">
          <div
            className="w-2 h-2 rounded-full opacity-50"
            style={{ background: "var(--green)" }}
          />
          <span>DAILY</span>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";

interface ActivityEvent {
  id: number;
  timestamp: string;
  type: string;
  strategy: string;
  market: string;
  side: string;
  amount: number;
  price: number;
  status: string;
  source_trader: string;
  message: string;
  details: string;
}

type TypeFilter = "all" | "trade" | "engine" | "error";
type StatusFilter = "all" | "executed" | "failed" | "dry_run";

export function ActivityLogPanel() {
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [search, setSearch] = useState("");

  // Build query params
  const queryParams = useMemo(() => {
    const params = new URLSearchParams();
    params.set("limit", "200");
    if (typeFilter === "trade") params.set("type", "trade");
    else if (typeFilter === "engine") params.set("type", "engine_start");
    else if (typeFilter === "error") params.set("type", "error");
    if (statusFilter !== "all") params.set("status", statusFilter);
    if (search.trim()) params.set("search", search.trim());
    return params.toString();
  }, [typeFilter, statusFilter, search]);

  const { data: events = [], isLoading } = useQuery<ActivityEvent[]>({
    queryKey: ["activity-log", queryParams],
    queryFn: () => apiJson(`/api/activity-log?${queryParams}`),
    refetchInterval: 10000,
  });

  // Client-side filter for engine events (since server filter is type-based)
  const filteredEvents = useMemo(() => {
    if (typeFilter === "engine") {
      return events.filter(
        (e) => e.type !== "trade"
      );
    }
    if (typeFilter === "error") {
      return events.filter(
        (e) =>
          e.type === "trade_failed" ||
          e.type === "poll_error" ||
          e.type === "error" ||
          e.type === "engine_error" ||
          e.status === "failed"
      );
    }
    return events;
  }, [events, typeFilter]);

  const typeColor = (type: string) => {
    switch (type) {
      case "trade":
        return "text-[var(--green)]";
      case "trade_copied":
        return "text-[var(--green)]";
      case "engine_start":
        return "text-[var(--cyan)]";
      case "engine_stop":
        return "text-[var(--cyan)]";
      case "initial_scan":
        return "text-[var(--cyan)]";
      case "scan_result":
        return "text-[var(--green-dim)]";
      case "trade_failed":
      case "poll_error":
      case "engine_error":
      case "error":
        return "text-[var(--red)]";
      default:
        return "text-[var(--green-dim)]";
    }
  };

  const typeBadge = (type: string) => {
    switch (type) {
      case "trade":
        return "TRADE";
      case "trade_copied":
        return "COPIED";
      case "trade_failed":
        return "FAIL";
      case "engine_start":
        return "START";
      case "engine_stop":
        return "STOP";
      case "initial_scan":
        return "SCAN";
      case "scan_result":
        return "SCAN";
      case "poll_error":
        return "ERR";
      case "engine_error":
        return "ERR";
      default:
        return type.toUpperCase().slice(0, 6);
    }
  };

  const statusColor = (status: string) => {
    switch (status) {
      case "executed":
        return "text-[var(--green)]";
      case "dry_run":
        return "text-[var(--amber)]";
      case "failed":
        return "text-[var(--red)]";
      default:
        return "text-[var(--green-dim)]";
    }
  };

  const truncate = (s: string | null, len: number) =>
    s ? (s.length > len ? s.slice(0, len) + "..." : s) : "";

  const formatTime = (ts: string) => {
    if (!ts) return "--";
    // Show date if not today, otherwise just time
    const today = new Date().toISOString().slice(0, 10);
    const dateStr = ts.slice(0, 10);
    if (dateStr === today) {
      return ts.slice(11, 19);
    }
    return ts.slice(5, 16).replace("T", " ");
  };

  // Summary stats
  const stats = useMemo(() => {
    const trades = filteredEvents.filter((e) => e.type === "trade");
    const errors = filteredEvents.filter(
      (e) =>
        e.type === "trade_failed" ||
        e.type === "poll_error" ||
        e.status === "failed"
    );
    const executed = trades.filter((e) => e.status === "executed");
    return {
      total: filteredEvents.length,
      trades: trades.length,
      executed: executed.length,
      errors: errors.length,
    };
  }, [filteredEvents]);

  const filterBtn = (
    label: string,
    active: boolean,
    onClick: () => void,
    color: string = "var(--green)"
  ) => (
    <button
      onClick={onClick}
      className={`px-2 py-1 text-[9px] font-bold uppercase tracking-wider border transition-colors ${
        active
          ? `bg-[${color}] text-black border-[${color}]`
          : `text-[var(--green-dim)] border-[var(--panel-border)] hover:border-[var(--green-dark)]`
      }`}
      style={
        active
          ? { backgroundColor: color, borderColor: color, color: "#000" }
          : undefined
      }
    >
      {label}
    </button>
  );

  return (
    <div className="space-y-4 slide-up">
      {/* Header + Stats */}
      <div className="glass rounded-none p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest">
            // ACTIVITY LOG
          </h3>
          <div className="flex items-center gap-2">
            <span className="blink text-[var(--green)] text-[8px]">&#9608;</span>
            <span className="text-[9px] text-[var(--green-dim)] mono">
              LIVE — {stats.total} events
            </span>
          </div>
        </div>

        {/* Stats row */}
        <div className="flex gap-4 text-[10px] mono mb-4">
          <span className="text-[var(--green-dim)]">
            TRADES: <span className="text-[var(--green)]">{stats.trades}</span>
          </span>
          <span className="text-[var(--green-dim)]">
            EXECUTED: <span className="text-[var(--green)]">{stats.executed}</span>
          </span>
          <span className="text-[var(--green-dim)]">
            ERRORS: <span className={stats.errors > 0 ? "text-[var(--red)]" : "text-[var(--green-dim)]"}>{stats.errors}</span>
          </span>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-2 items-center">
          {/* Type filter */}
          <div className="flex gap-1">
            {filterBtn("ALL", typeFilter === "all", () => setTypeFilter("all"))}
            {filterBtn("TRADES", typeFilter === "trade", () => setTypeFilter("trade"))}
            {filterBtn("ENGINE", typeFilter === "engine", () => setTypeFilter("engine"), "var(--cyan)")}
            {filterBtn("ERRORS", typeFilter === "error", () => setTypeFilter("error"), "var(--red)")}
          </div>

          <span className="text-[var(--panel-border)]">|</span>

          {/* Status filter */}
          <div className="flex gap-1">
            {filterBtn("ALL", statusFilter === "all", () => setStatusFilter("all"))}
            {filterBtn("OK", statusFilter === "executed", () => setStatusFilter("executed"))}
            {filterBtn("FAILED", statusFilter === "failed", () => setStatusFilter("failed"), "var(--red)")}
            {filterBtn("DRY", statusFilter === "dry_run", () => setStatusFilter("dry_run"), "var(--amber)")}
          </div>

          <span className="text-[var(--panel-border)]">|</span>

          {/* Search */}
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="search markets..."
            className="bg-transparent border border-[var(--panel-border)] text-[var(--green)] text-[10px] mono px-2 py-1 w-40 focus:border-[var(--green)] outline-none placeholder:text-[var(--green-dark)]"
          />
        </div>
      </div>

      {/* Event table */}
      <div className="glass rounded-none p-4">
        <div className="overflow-x-auto">
          <table className="w-full text-xs mono">
            <thead>
              <tr className="text-[9px] text-[var(--green-dark)] uppercase tracking-wider">
                <th className="text-left pb-2 pr-2 w-[70px]">TIME</th>
                <th className="text-left pb-2 pr-2 w-[55px]">TYPE</th>
                <th className="text-left pb-2 pr-2 w-[40px]">STR</th>
                <th className="text-left pb-2 pr-2">MARKET / MESSAGE</th>
                <th className="text-left pb-2 pr-2 w-[35px]">SIDE</th>
                <th className="text-right pb-2 pr-2 w-[60px]">AMT</th>
                <th className="text-left pb-2 pr-2 w-[80px]">FROM</th>
                <th className="text-left pb-2 w-[55px]">STATUS</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="text-center text-[var(--green-dim)] py-8 mono">
                    loading<span className="blink">_</span>
                  </td>
                </tr>
              ) : filteredEvents.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center text-[var(--green-dark)] py-8 mono">
                    -- no events --
                  </td>
                </tr>
              ) : (
                filteredEvents.map((e, idx) => {
                  const isTradeRow = e.type === "trade";
                  const displayText = isTradeRow
                    ? truncate(e.market, 40)
                    : truncate(e.message, 60);

                  return (
                    <tr
                      key={`${e.type}-${e.id}-${idx}`}
                      className="border-t border-[rgba(0,255,65,0.06)] hover:bg-[rgba(0,255,65,0.04)]"
                    >
                      {/* Time */}
                      <td className="py-1.5 pr-2 text-[var(--green-dim)] text-[10px]">
                        {formatTime(e.timestamp)}
                      </td>

                      {/* Type badge */}
                      <td className="py-1.5 pr-2">
                        <span
                          className={`${typeColor(e.type)} text-[9px] font-bold`}
                        >
                          [{typeBadge(e.type)}]
                        </span>
                      </td>

                      {/* Strategy */}
                      <td className="py-1.5 pr-2 text-[var(--green-dark)] text-[9px]">
                        {e.strategy ? e.strategy.slice(0, 4).toUpperCase() : ""}
                      </td>

                      {/* Market / Message */}
                      <td className="py-1.5 pr-2 text-[var(--green)]">
                        {displayText || "--"}
                      </td>

                      {/* Side */}
                      <td className="py-1.5 pr-2">
                        {e.side ? (
                          <span
                            className={
                              e.side === "BUY"
                                ? "text-[var(--green)]"
                                : "text-[var(--red)]"
                            }
                          >
                            {e.side}
                          </span>
                        ) : null}
                      </td>

                      {/* Amount */}
                      <td className="py-1.5 pr-2 text-right text-[var(--cyan)]">
                        {e.amount > 0 ? `$${e.amount.toFixed(2)}` : ""}
                      </td>

                      {/* From (source trader) */}
                      <td className="py-1.5 pr-2 text-[var(--magenta)] text-[10px]">
                        {e.source_trader
                          ? `${e.source_trader.slice(0, 6)}...${e.source_trader.slice(-4)}`
                          : ""}
                      </td>

                      {/* Status */}
                      <td className={`py-1.5 text-[10px] ${statusColor(e.status)}`}>
                        {e.status || ""}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Mobile card layout for small screens */}
      <div className="sm:hidden space-y-2">
        {filteredEvents.slice(0, 50).map((e, idx) => {
          const isTradeRow = e.type === "trade";
          return (
            <div
              key={`mobile-${e.type}-${e.id}-${idx}`}
              className="glass rounded-none p-3 border-l-2"
              style={{
                borderLeftColor:
                  e.status === "failed" || e.type.includes("error")
                    ? "var(--red)"
                    : e.status === "dry_run"
                    ? "var(--amber)"
                    : e.type.includes("engine") || e.type === "initial_scan"
                    ? "var(--cyan)"
                    : "var(--green)",
              }}
            >
              <div className="flex justify-between items-center mb-1">
                <span className={`${typeColor(e.type)} text-[9px] font-bold`}>
                  [{typeBadge(e.type)}]
                </span>
                <span className="text-[9px] text-[var(--green-dim)]">
                  {formatTime(e.timestamp)}
                </span>
              </div>
              <div className="text-[11px] text-[var(--green)] mb-1">
                {isTradeRow ? truncate(e.market, 50) : truncate(e.message, 60)}
              </div>
              <div className="flex gap-3 text-[9px]">
                {e.side && (
                  <span
                    className={
                      e.side === "BUY"
                        ? "text-[var(--green)]"
                        : "text-[var(--red)]"
                    }
                  >
                    {e.side}
                  </span>
                )}
                {e.amount > 0 && (
                  <span className="text-[var(--cyan)]">
                    ${e.amount.toFixed(2)}
                  </span>
                )}
                {e.source_trader && (
                  <span className="text-[var(--magenta)]">
                    {e.source_trader.slice(0, 8)}...
                  </span>
                )}
                {e.status && (
                  <span className={statusColor(e.status)}>{e.status}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
